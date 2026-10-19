"""CP3 fixed-design, single-look synthetic experiment evidence CLI."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from product_analytics.data.synthetic_events import SCENARIOS, generate_events
from product_analytics.experimentation.cp3_analysis import (
    load_locked_design, analyze_experiment, cuped_separate_demo, DESIGN_HASH)


def build_cp3_evidence(*,scenario='positive',n_users=6000,seed=1703,out_dir=Path('artifacts/cp3')) -> dict:
    if scenario not in ('positive','null','srm','underpowered','baseline'):
        raise ValueError('CP3 scenario must be positive/null/srm/underpowered/baseline')
    # Mandatory check BEFORE reading outcomes or generating a trial.
    design=load_locked_design()
    if scenario=='underpowered' and n_users>60:
        raise ValueError('underpowered uses 60 or fewer randomized users')
    frame=generate_events(n_users,seed,scenario)
    result=analyze_experiment(frame,design)
    result.update({'checkpoint':'CP3','scenario':scenario,'seed':seed,'requested_users':n_users,
                   'synthetic_data_only':True,'analysis_look':'one_fixed_look',
                   'preregistration_checked_before_generation':True,
                   'preregistration_sha256':DESIGN_HASH,'live_deployment':False,
                   'observed_effect_is_real_world_evidence':False,'bigquery_executed':False,
                   'cuped_separate_demo':cuped_separate_demo()})
    out_dir=Path(out_dir)
    out_dir.mkdir(parents=True,exist_ok=True)
    events=out_dir/'cp3_synthetic_events.csv';events.write_text(frame.to_csv(index=False,lineterminator='\n'),encoding='utf-8')
    result['input_event_csv_sha256']=sha256(events.read_bytes()).hexdigest()
    report=out_dir/'cp3_report.json';report.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description='CP3 locked-design A/B, SRM, guardrail, CUPED demo and subgroup checks')
    p.add_argument('--scenario',choices=['positive','null','srm','underpowered','baseline'],default='positive')
    p.add_argument('--users',type=int,default=6000)
    p.add_argument('--seed',type=int,default=1703)
    p.add_argument('--out-dir',type=Path,default=Path('artifacts/cp3'))
    args=p.parse_args(argv)
    try:
        r=build_cp3_evidence(scenario=args.scenario,n_users=args.users,seed=args.seed,out_dir=args.out_dir)
    except (ValueError,KeyError,AssertionError,OSError) as exc:
        print(f'CP3 BLOCKED: {exc}',file=sys.stderr)
        return 2
    print(json.dumps({'checkpoint':'CP3','scenario':args.scenario,'design_lock':r['preregistration_sha256'],
                      'randomization':r['randomization']['exact_binomial_srm_p'],
                      'primary':r['primary_outcome'],
                      'release_decision':r['release_decision'],
                      'out_dir':str(args.out_dir)},indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
