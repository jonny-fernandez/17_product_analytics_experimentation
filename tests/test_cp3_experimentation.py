"""CP3 fixed-design inference, adversarial controls and deterministic reproducibility."""
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from product_analytics.data.synthetic_events import generate_events
from product_analytics.data.cp3_report import build_cp3_evidence
from product_analytics.experimentation.cp3_analysis import (
    load_locked_design, analyze_experiment, cuped_separate_demo,
    _diff_estimate, _holm_interactions, DESIGN_HASH,
)

@pytest.fixture(scope='module')
def locked():
    return load_locked_design()

@pytest.fixture(scope='module')
def positive():
    return generate_events(900,1337,'positive')

@pytest.fixture(scope='module')
def null():
    return generate_events(900,1337,'null')

@pytest.fixture(scope='module')
def srm():
    return generate_events(900,1337,'srm')


def test_locked_design_is_valid(locked):
    assert locked['design_id'].startswith('CP3-V1-LOCKED')
    assert locked['primary']['absolute_mde']==.005
    assert locked['exposure_gate'].startswith('exactly_one')


def test_tampered_design_is_blocked(tmp_path):
    p=tmp_path/'design.json'
    p.write_text('{"primary": {"alpha": 0.99}}')
    with pytest.raises(ValueError,match='PREREGISTRATION_MISMATCH'):
        load_locked_design(p)


def test_positive_synthetic_has_correct_fields(positive,locked):
    r=analyze_experiment(positive,locked)
    assert r['population']['n_A']+r['population']['n_B']==900
    assert r['design']['planned_n_per_arm']==57756
    assert r['primary_outcome']['confidence_level']==.95
    assert r['release_decision']['status']=='BLOCK_RELEASE'
    assert r['design']['achieved_planned_sample'] is False


def test_null_not_forced_positive(null,locked):
    r=analyze_experiment(null,locked)
    assert r['primary_outcome']['p_value']>=0
    assert r['primary_outcome']['p_value']<=1
    assert r['release_decision']['status']=='BLOCK_RELEASE'


def test_srm_blocked(srm,locked):
    r=analyze_experiment(srm,locked)
    assert r['randomization']['srm_failed'] is True
    assert 'SRM_FAIL' in r['release_decision']['blocking_reasons']


def test_no_exposure_selection(positive,locked):
    frame=positive.copy()
    i=frame.index[frame.event_name=='experiment_exposure'][0]
    frame=frame.drop(index=i)
    with pytest.raises(ValueError,match='QUALITY_GATE_FAILED|ITT_EXPOSURE'):
        analyze_experiment(frame,locked)


def test_incomplete_observation_blocks(positive,locked):
    with pytest.raises(ValueError,match='ITT_EXPOSURE_OR_FOLLOWUP_SELECTION_GATE_FAILED'):
        analyze_experiment(positive,locked,observation_end=datetime(2026,1,20,tzinfo=timezone.utc))


def test_missing_assignment_blocks(positive,locked):
    frame=positive.loc[~((positive.user_id==positive.user_id.iloc[0]) &
                           (positive.event_name=='experiment_assignment'))]
    with pytest.raises(ValueError,match='QUALITY_GATE_FAILED'):
        analyze_experiment(frame,locked)


def test_duplicate_assignment_blocks(positive,locked):
    frame=pd.concat([positive,positive.iloc[[0]]],ignore_index=True)
    with pytest.raises(ValueError,match='QUALITY_GATE_FAILED'):
        analyze_experiment(frame,locked)


def test_negative_revenue_blocks(positive,locked):
    frame=positive.copy()
    i=frame.index[frame.event_name=='purchase'][0]
    frame.loc[i,'revenue']=-5
    with pytest.raises(ValueError,match='QUALITY_GATE_FAILED'):
        analyze_experiment(frame,locked)


def test_timestamp_drift_blocks(positive,locked):
    frame=positive.copy()
    frame['event_timestamp']=frame.event_timestamp.astype(object)
    t=frame.loc[frame.index[0],'event_timestamp']
    frame.at[frame.index[0],'event_timestamp']=t.replace(tzinfo=None)
    with pytest.raises(ValueError,match='QUALITY_GATE_FAILED'):
        analyze_experiment(frame,locked)


def test_balanced_positive_not_srm(positive,locked):
    r=analyze_experiment(positive,locked)
    assert not r['randomization']['srm_failed']


def test_guards_were_prespecified(positive,locked):
    r=analyze_experiment(positive,locked)
    assert {x['metric'] for x in r['guardrails']}==set(locked['guardrails'])
    assert all(x['upper_bound_confidence_level']==pytest.approx(.9875) for x in r['guardrails'])


def test_interactions_declared_before_testing(positive,locked):
    r=analyze_experiment(positive,locked)
    tests=r['subgroup_interaction_tests']
    assert len(tests)==8
    assert all(t['predeclared'] for t in tests)
    assert all(t['holm_adjusted_p'] is None or t['holm_adjusted_p']>=t['raw_p'] for t in tests)


def test_subgroup_missing_arm_not_invented(positive,locked):
    user=__import__('product_analytics.metrics.product',fromlist=['make_user_metrics']).make_user_metrics(positive)
    user.loc[(user.device=='tablet')&(user.variant=='B'),'variant']='A'
    tests=_holm_interactions(user,locked)
    tablet=next(t for t in tests if t['dimension']=='device' and t['value']=='tablet')
    assert tablet['status']=='INSUFFICIENT_DATA'
    assert tablet['holm_adjusted_p'] is None


def test_cuped_demo_separate_and_reduces_variance():
    r=cuped_separate_demo()
    assert r['fixture']=='SEPARATE_SYNTHETIC_CONTINUOUS_DEMO_NOT_PRIMARY'
    assert r['variance_cuped']<r['variance_unadjusted']
    assert r['relative_variance_reduction']>.5


def test_cuped_primary_skipped(positive,locked):
    r=analyze_experiment(positive,locked)
    assert r['cuped']['applied_to_primary'] is False


def test_zero_count_ci_and_exact_test():
    a=pd.DataFrame({'x':[0]*30})
    b=pd.DataFrame({'x':[0]*30})
    r=_diff_estimate(b,a,'x')
    assert r['p_value']==1.0
    assert r['test']=='fisher_exact_small_counts'
    assert r['confidence_interval_absolute_difference'][0]<0


def test_source_nonnumeric_outcome_blocks():
    a=pd.DataFrame({'x':[0,1]})
    b=pd.DataFrame({'x':[3,1]})
    with pytest.raises(ValueError,match='invalid binary'):
        _diff_estimate(b,a,'x')


def test_report_writes_all_hashes_and_is_repeatable(tmp_path):
    r1=build_cp3_evidence(scenario='underpowered',n_users=60,seed=101,out_dir=tmp_path/'one')
    r2=build_cp3_evidence(scenario='underpowered',n_users=60,seed=101,out_dir=tmp_path/'two')
    assert r1==r2
    assert r1['preregistration_sha256']==DESIGN_HASH
    assert r1['population']['assigned_users']==60
    assert (tmp_path/'one'/'cp3_synthetic_events.csv').read_bytes()==(tmp_path/'two'/'cp3_synthetic_events.csv').read_bytes()
    assert r1['release_decision']['status']=='BLOCK_RELEASE'


def test_contaminated_not_accepted(tmp_path):
    with pytest.raises(ValueError,match='CP3 scenario must'):
        build_cp3_evidence(scenario='contaminated',n_users=60,out_dir=tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_underpowered_limit(tmp_path):
    with pytest.raises(ValueError,match='60 or fewer'):
        build_cp3_evidence(scenario='underpowered',n_users=100,out_dir=tmp_path/'bad')


def test_incomplete_followup_newcohorts_never_silent(positive,locked):
    frame=positive.copy()
    # Retiming latest assignment/observation to post-window would breach full followup.
    with pytest.raises(ValueError,match='ITT_EXPOSURE'):
        analyze_experiment(frame,locked,observation_end=datetime(2026,1,1,tzinfo=timezone.utc))

@pytest.mark.parametrize('randomized,documented,allowed',[
    (False,False,False),(False,True,False),(True,False,False),(True,True,True),
])
def test_causal_claim_gate(randomized,documented,allowed):
    from product_analytics.causal.measurement import causal_claim_allowed
    assert causal_claim_allowed(randomized,documented) is allowed
