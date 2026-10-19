"""Frozen-design synthetic randomized A/B evaluation; deterministic statistics, no services."""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm, fisher_exact, chisquare
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest
from product_analytics.data.validation import validate_event_frame
from product_analytics.metrics.product import make_user_metrics, DEFAULT_OBSERVATION_END
from product_analytics.experimentation.power import required_sample_per_group

DESIGN_HASH = '83f26f31c75188df1b2a21c1afaa00b0c0a806e325ff80795035fcf2920af40a'
DESIGN_FILE = Path(__file__).resolve().parents[3] / 'configs/cp3_preregistered_design.json'


def load_locked_design(path: Path = DESIGN_FILE) -> dict:
    """Verify expected bytes before any outcome generation/reading; local, unsigned lock."""
    actual = sha256(path.read_bytes()).hexdigest()
    if actual != DESIGN_HASH:
        raise ValueError(f'PREREGISTRATION_MISMATCH: expected {DESIGN_HASH}, observed {actual}')
    design = json.loads(path.read_text(encoding='utf-8'))
    assert design['design_id']=='CP3-V1-LOCKED-SYNTHETIC-2026-10-19'
    return design


def _counts(frame: pd.DataFrame, column: str) -> tuple[int, int]:
    if not frame[column].isin([0, 1]).all():
        raise ValueError(f'invalid binary outcome {column}')
    return int(frame[column].sum()), len(frame)


def _diff_estimate(b: pd.DataFrame, a: pd.DataFrame, column: str, alpha: float=.05) -> dict:
    nb, db = _counts(b, column)
    na, da = _counts(a, column)
    if not db or not da:
        raise ValueError('Empty experiment arm')
    pb, pa = nb/db, na/da
    # Newcombe score-based CI is stable for zero or all conversions.
    ci = confint_proportions_2indep(nb, db, na, da, compare='diff', method='newcomb', alpha=alpha)
    if min(nb,db-nb,na,da-na)<5:
        _,pvalue=fisher_exact([[nb,db-nb],[na,da-na]],alternative='two-sided')
        method='fisher_exact_small_counts'
        statistic=None
    else:
        statistic,pvalue=proportions_ztest([nb,na],[db,da],alternative='two-sided')
        method='pooled_two_proportion_z'
    return {
        'n_A':da,'n_B':db,'successes_A':na,'successes_B':nb,
        'rate_A':pa,'rate_B':pb,'absolute_difference_B_minus_A':pb-pa,
        'relative_lift_vs_A':None if pa==0 else pb/pa-1,
        'confidence_interval_absolute_difference':[float(ci[0]),float(ci[1])],
        'confidence_level':1-alpha,'test':method,
        'test_statistic':None if statistic is None else float(statistic),'p_value':float(pvalue),
    }


def _holm_interactions(users: pd.DataFrame, design:dict) -> list[dict]:
    rows=[]
    for dimension, values in design['subgroup_dimensions'].items():
        for value in values:
            group=users[users[dimension]==value]
            rest=users[users[dimension]!=value]
            record={'dimension':dimension,'value':value,'n_group':int(len(group)),
                    'n_complement':int(len(rest)), 'predeclared':True}
            arms=[]
            for part in (group,rest):
                a=part[part.variant=='A'];b=part[part.variant=='B']
                if min(len(a),len(b))<2:
                    break
                pa,pb=a.purchased_7d.mean(),b.purchased_7d.mean()
                variance=float(pa*(1-pa)/len(a)+pb*(1-pb)/len(b))
                arms.append((float(pb-pa),variance))
            if len(arms)<2 or sum(x[1] for x in arms)<=0:
                record.update({'interaction_effect':None,'raw_p':None,'holm_adjusted_p':None,'status':'INSUFFICIENT_DATA'})
            else:
                eff=arms[0][0]-arms[1][0]
                p=float(2*norm.sf(abs(eff/math.sqrt(arms[0][1]+arms[1][1]))))
                record.update({'interaction_effect':eff,'raw_p':p,'holm_adjusted_p':None,'status':'exploratory_only'})
            rows.append(record)
    indexed=[i for i,r in enumerate(rows) if r['raw_p'] is not None]
    if indexed:
        adjusted=multipletests([rows[i]['raw_p'] for i in indexed],alpha=.05,method='holm')[1]
        for i,p in zip(indexed,adjusted):
            rows[i]['holm_adjusted_p']=float(p)
    return rows


def _assignment_balance(assignments:pd.DataFrame) -> list[dict]:
    out=[]
    for col in ('device','channel'):
        tab=pd.crosstab(assignments[col],assignments.variant)
        if set(['A','B'])-set(tab.columns):
            p=None
        elif tab.shape[0] < 2:
            p=None
        else:
            _,p,_,_=__import__('scipy').stats.chi2_contingency(tab.to_numpy(),correction=False)
            p=float(p)
        out.append({'dimension':col,'chi_square_p':p,'diagnostic_only':True})
    return out


def analyze_experiment(frame:pd.DataFrame, design:dict, *, observation_end=DEFAULT_OBSERVATION_END) -> dict:
    """No statistical inference on invalid, filtered or immature randomized cohorts."""
    quality=validate_event_frame(frame)
    if not quality['valid']:
        raise ValueError(f'QUALITY_GATE_FAILED: {quality["error_codes"]}')
    assignments=frame.loc[frame.event_name=='experiment_assignment', ['user_id','variant','device','channel']]
    if not assignments.user_id.is_unique:
        raise ValueError('DUPLICATE_ASSIGNMENTS')
    n_assigned=len(assignments)
    if n_assigned<2:
        raise ValueError('INSUFFICIENT_ASSIGNED_USERS')
    users=make_user_metrics(frame,observation_end=observation_end)
    # Critical selection-bias and maturity gate; prohibit postassignment cohort filtering.
    if len(users)!=n_assigned or set(users.user_id)!=set(assignments.user_id):
        raise ValueError('ITT_EXPOSURE_OR_FOLLOWUP_SELECTION_GATE_FAILED: one complete 7d follow-up per assigned user required')
    merged=users.merge(assignments,on='user_id',suffixes=('','_assigned'),validate='one_to_one')
    if not (merged.variant==merged.variant_assigned).all():
        raise ValueError('ASSIGNMENT_VARIANT_MISMATCH')
    for col in ('channel','device'):
        if not (merged[col]==merged[col+'_assigned']).all():
            raise ValueError(f'PREASSIGNMENT_STRATIFICATION_MISMATCH: {col}')
    a=users.loc[users.variant=='A'];b=users.loc[users.variant=='B']
    if not len(a) or not len(b):
        raise ValueError('EMPTY_ARM')
    n_b=len(b)
    observed={'A':len(a),'B':n_b}
    srm_p=float(binomtest(n_b,n_assigned,design['allocation']['B'],alternative='two-sided').pvalue)
    srm_fail=srm_p<design['srm_exact_two_sided_alpha']
    pdesign=design['primary']; alpha=pdesign['alpha']
    planned_n=required_sample_per_group(pdesign['baseline_planning_probability'],
               pdesign['baseline_planning_probability']+pdesign['absolute_mde'],alpha,pdesign['desired_power'])
    primary=_diff_estimate(b,a,'purchased_7d',alpha)
    primary['significant_at_locked_alpha']=primary['p_value']<alpha
    guards=[]
    # Familywise one-sided alpha .025 split across 2 guardrails. Newcombe two-sided
    # 97.5% interval upper endpoint is a conservative one-sided 98.75% upper limit.
    upper_alpha=design['guardrails_familywise_one_sided_alpha']/len(design['guardrails'])
    for metric,policy in design['guardrails'].items():
        bounds=_diff_estimate(b,a,metric,2*upper_alpha)
        upper=bounds['confidence_interval_absolute_difference'][1]
        tolerance=policy['maximum_absolute_risk_increase']
        guards.append({'metric':metric,'risk_tolerance_absolute':tolerance,
                       'observed_difference_B_minus_A':bounds['absolute_difference_B_minus_A'],
                       'conservative_one_sided_upper_bound':upper,
                       'upper_bound_confidence_level':1-upper_alpha,
                       'passes_noninferiority':bool(upper<tolerance),
                       'group_successes_A':bounds['successes_A'],'group_successes_B':bounds['successes_B']})
    sample_ok=min(len(a),len(b))>=planned_n
    reasons=[]
    if srm_fail: reasons.append('SRM_FAIL')
    if not sample_ok: reasons.append('BELOW_PLANNED_MDE_SAMPLE_SIZE')
    if not primary['significant_at_locked_alpha']: reasons.append('PRIMARY_NOT_STATISTICALLY_SIGNIFICANT')
    if not all(g['passes_noninferiority'] for g in guards): reasons.append('GUARDRAILS_NOT_CLEARED')
    return {
      'data_quality':quality,'population':{'assigned_users':n_assigned,'analyzed_users':len(users),
          'n_A':len(a),'n_B':len(b),'ITT_population_invariant':True,'complete_seven_day_followup':True},
      'design':{'locked_design_sha256':DESIGN_HASH,'alpha':alpha,'target_power':pdesign['desired_power'],
          'baseline_planning_rate':pdesign['baseline_planning_probability'],
          'relative_mde':pdesign['relative_mde'],'absolute_mde':pdesign['absolute_mde'],
          'planned_n_per_arm':planned_n,'planned_total_n':2*planned_n,
          'achieved_planned_sample':sample_ok,'interim_looks':0},
      'randomization':{'expected_allocation':design['allocation'],'observed':observed,
           'exact_binomial_srm_p':srm_p,'srm_threshold':design['srm_exact_two_sided_alpha'],
           'srm_failed':srm_fail,'covariate_balance_descriptive_only':_assignment_balance(assignments)},
      'primary_outcome':primary,'guardrails':guards,'subgroup_interaction_tests':_holm_interactions(users,design),
      'cuped':{'applied_to_primary':False,'reason':'No verified preassignment covariate in the CP2 GA4-style event contract.'},
      'causal_qualification':{'synthetic_randomization_in_generator':True,'real_world_causal_impact_estimated':False,
          'observational_attribution_treated_as_causal':False},
      'release_decision':{'status':'BLOCK_RELEASE' if reasons else 'ELIGIBLE_FOR_MANUAL_REVIEW_NOT_AUTO_RELEASE',
                          'blocking_reasons':reasons},
    }


def cuped_separate_demo(seed:int=783, n:int=2000) -> dict:
    """Independent continuous synthetic outcome DGP; NOT a CP3 conversion adjustment."""
    from product_analytics.experimentation.cuped import cuped_adjust
    rng=np.random.default_rng(seed)
    pre=rng.normal(0,1,n)              # explicitly generated before treatment
    treatment=rng.integers(0,2,n)        # independent randomized assignment
    outcome=20+4*pre+0.3*treatment+rng.normal(0,2,n)
    adjusted=cuped_adjust(outcome,pre)
    def variance_of_diff(y):
        return float(y[treatment==1].var(ddof=1)/sum(treatment==1)+
                     y[treatment==0].var(ddof=1)/sum(treatment==0))
    raw=variance_of_diff(outcome); adj=variance_of_diff(adjusted)
    return {'fixture':'SEPARATE_SYNTHETIC_CONTINUOUS_DEMO_NOT_PRIMARY',
            'n':n,'raw_difference':float(outcome[treatment==1].mean()-outcome[treatment==0].mean()),
            'adjusted_difference':float(adjusted[treatment==1].mean()-adjusted[treatment==0].mean()),
            'variance_unadjusted':raw,'variance_cuped':adj,
            'relative_variance_reduction':float(1-adj/raw),
            'pre_assignment_covariate':True,'crossfit_or_preestimated_theta':False,
            'warning':'Demonstration only; no inference from this CUPED demo applied to event-based conversion.'}
