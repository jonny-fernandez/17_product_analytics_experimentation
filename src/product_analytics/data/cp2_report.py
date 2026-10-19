"""CP2 CLI generates reproducible descriptive analytics and independent SQLite parity evidence."""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
import pandas as pd

from product_analytics.data.synthetic_events import SCENARIOS, generate_events
from product_analytics.data.validation import validate_event_frame
from product_analytics.metrics.product import DEFAULT_OBSERVATION_END, make_user_metrics, compute_tables
from product_analytics.metrics.sql_parity import check_sql_parity
from product_analytics.metrics.dashboard import render_dashboard


def _write_csv(path: Path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, lineterminator='\n')


def build_cp2_evidence(*, scenario: str='baseline', n_users: int=500, seed: int=42,
                       out_dir: Path=Path('artifacts/cp2'), observation_end: datetime=DEFAULT_OBSERVATION_END) -> dict:
    """Reject intentionally invalid CP1 scenarios before saving any measured outputs."""
    if scenario not in SCENARIOS:
        raise ValueError(f'Unknown scenario: {scenario}')
    frame = generate_events(n_users, seed, scenario)
    quality = validate_event_frame(frame)
    if not quality['valid']:
        raise ValueError(f'Source quality gate rejected {scenario}: {quality["error_codes"]}')
    users = make_user_metrics(frame, observation_end)
    tables = compute_tables(users, observation_end)
    parity = check_sql_parity(frame, users, observation_end)
    if not parity['passed']:
        raise RuntimeError(f'SQL/Python parity mismatch: {parity["mismatches"]}')
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        'synthetic_events.csv': out_dir / 'cp2_synthetic_events.csv',
        'user_metrics.csv': out_dir / 'cp2_user_metrics.csv',
        'funnel.csv': out_dir / 'cp2_funnel.csv',
        'cohort_retention.csv': out_dir / 'cp2_cohort_retention.csv',
        'segments.csv': out_dir / 'cp2_segments.csv',
        'attribution.csv': out_dir / 'cp2_attribution.csv',
        'dashboard.html': out_dir / 'cp2_dashboard.html',
    }
    frame.to_csv(paths['synthetic_events.csv'], index=False, lineterminator='\n')
    # Keep user-grain touch arrays out of the CSV; explicit modeled counts are in report.
    users.drop(columns=['touches']).to_csv(paths['user_metrics.csv'], index=False, lineterminator='\n')
    for file, key in [('funnel.csv','funnel'), ('cohort_retention.csv','retention'),
                      ('segments.csv','segments'),('attribution.csv','attribution')]:
        _write_csv(paths[file], tables[key])
    paths['dashboard.html'].write_text(render_dashboard(tables, scenario, seed, parity), encoding='utf-8')
    result = {
        'checkpoint': 'CP2', 'scenario': scenario, 'seed': seed, 'requested_users': n_users,
        'observation_end_utc': observation_end.isoformat(), 'data_classification': 'synthetic offline fixture only',
        'data_quality': quality, 'sql_parity': parity, 'summary': tables['summary'],
        'journeys': tables['journeys'], 'funnel': tables['funnel'],
        'cohort_count': users.cohort_day.nunique(), 'segments': tables['segments'],
        'attribution': tables['attribution'],
        'artifacts_sha256': {name: sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        'attribution_is_causal': False, 'statistical_inference_performed': False,
        'bigquery_executed': False, 'local_dashboard_generated': True,
    }
    (out_dir/'cp2_report.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    return result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Offline product metrics, SQLite parity and local HTML dashboard')
    p.add_argument('--scenario', choices=sorted(SCENARIOS), default='baseline')
    p.add_argument('--users', type=int, default=500)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--out-dir', type=Path, default=Path('artifacts/cp2'))
    p.add_argument('--observation-end', default=DEFAULT_OBSERVATION_END.isoformat())
    args = p.parse_args(argv)
    try:
        end = datetime.fromisoformat(args.observation_end)
        result = build_cp2_evidence(scenario=args.scenario, n_users=args.users, seed=args.seed,
                                    out_dir=args.out_dir, observation_end=end)
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'CP2 ERROR: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'checkpoint': 'CP2', 'scenario': args.scenario, 'summary': result['summary'],
                      'sql_parity': result['sql_parity'], 'out_dir': str(args.out_dir)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
