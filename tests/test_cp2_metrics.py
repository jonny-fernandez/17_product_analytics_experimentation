"""CP2 regression and adversarial tests: descriptive metrics, parity, completeness and rejects."""
from datetime import datetime, timedelta, timezone
import json
import pandas as pd
import pytest

from product_analytics.data.synthetic_events import generate_events
from product_analytics.data.cp2_report import build_cp2_evidence
from product_analytics.metrics.product import DEFAULT_OBSERVATION_END, make_user_metrics, compute_tables
from product_analytics.metrics.sql_parity import check_sql_parity


@pytest.fixture(scope='module')
def baseline():
    return generate_events(500, 42)


@pytest.fixture(scope='module')
def users(baseline):
    return make_user_metrics(baseline)


def test_baseline_users(baseline, users):
    assert len(users) == 500
    assert users.user_id.is_unique
    assert users.purchased_7d.isin([0, 1]).all()
    assert users.sessions_7d.max() == 2
    assert users.sessions_7d.min() == 1


def test_funnel_ordered_decreasing(users):
    t = compute_tables(users)
    counts = [row['users'] for row in t['funnel']]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] == 500
    assert counts[-1] == int(users.funnel_purchase.sum())


def test_7d_purchase_denominator(users):
    summary = compute_tables(users)['summary']
    assert summary['purchase_conversion_7d'] == users.purchased_7d.mean()
    assert summary['revenue_per_exposed_user'] == users.revenue_7d.sum() / len(users)


def test_retention_bounds(users):
    t = compute_tables(users)
    assert len(t['retention']) == users.cohort_day.nunique() * 7
    assert all(x['retention_rate'] is None or 0 <= x['retention_rate'] <= 1 for x in t['retention'])
    assert any(row['returning_users'] > 0 for row in t['retention'])


def test_attribution_conserves_credit(users):
    t = compute_tables(users)
    buyer_n = int(users.purchased_7d.sum())
    revenue = float(users.revenue_7d.sum())
    for model in ('first_touch', 'last_touch', 'linear_multitouch'):
        rows = [r for r in t['attribution'] if r['model'] == model]
        assert sum(r['buyer_credit'] for r in rows) == pytest.approx(buyer_n)
        assert sum(r['revenue_credit'] for r in rows) == pytest.approx(revenue)
    assert t['journeys']['multichannel_users'] > 0


def test_sql_parity(baseline, users):
    r = check_sql_parity(baseline, users, DEFAULT_OBSERVATION_END)
    assert r['passed'], r
    assert r['python_users'] == r['sql_users'] == 500


@pytest.mark.parametrize('scenario,users_count',[('null', 200), ('positive', 200),('srm',200),('underpowered',50)])
def test_sql_parity_other_valid_scenarios(scenario, users_count):
    frame = generate_events(users_count, 42, scenario)
    result = check_sql_parity(frame, make_user_metrics(frame), DEFAULT_OBSERVATION_END)
    assert result['passed'], result


def test_invalid_duplicate_fails_closed(baseline):
    invalid = pd.concat([baseline, baseline.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match='duplicate_event_id'):
        make_user_metrics(invalid)


def test_missing_exposure_fails_closed(baseline):
    invalid = baseline.drop(baseline.index[baseline.event_name=='experiment_exposure'][0])
    with pytest.raises(ValueError, match='exposure_count'):
        make_user_metrics(invalid)


def test_duplicate_user_assignment_fails_closed(baseline):
    copy = baseline.iloc[[0]].copy()
    copy.loc[copy.index[0], 'event_id'] = 'assignment_added'
    with pytest.raises(ValueError, match='assignment_count'):
        make_user_metrics(pd.concat([baseline,copy], ignore_index=True))


def test_invalid_conversion_fails_closed(baseline):
    invalid = baseline.copy()
    invalid.loc[invalid.index[1], 'conversion'] = 1
    with pytest.raises(ValueError, match='schema_error'):
        make_user_metrics(invalid)


def test_timezone_shift_fails_closed(baseline):
    invalid = baseline.copy()
    i = invalid.index[0]
    invalid['event_timestamp'] = invalid.event_timestamp.astype(object)
    invalid.at[i,'event_timestamp'] = invalid.at[i,'event_timestamp'].replace(tzinfo=None)
    with pytest.raises(ValueError, match='schema_error'):
        make_user_metrics(invalid)


def test_immature_outcome_drops_eligible_users(baseline):
    end = datetime(2026, 1, 15, tzinfo=timezone.utc)
    users = make_user_metrics(baseline, end)
    assert 0 < len(users) < 500
    assert all(datetime.fromisoformat(x) + timedelta(days=7) <= end for x in users.exposure_ts)


def test_immature_cohort_return_not_zero(baseline):
    end = datetime(2026, 1, 8, 12, tzinfo=timezone.utc)
    users = make_user_metrics(baseline, end)
    t = compute_tables(users, end)
    assert any(r['retention_rate'] is None for r in t['retention'])


def test_bad_observation_time_rejected(baseline):
    with pytest.raises(ValueError, match='UTC-aware'):
        make_user_metrics(baseline, datetime(2026,2,9))


def test_evidence_repeatable(tmp_path):
    a = build_cp2_evidence(out_dir=tmp_path/'a')
    b = build_cp2_evidence(out_dir=tmp_path/'b')
    assert a == b
    assert a['sql_parity']['passed']
    assert (tmp_path/'a'/'cp2_dashboard.html').exists()
    assert '<script' not in (tmp_path/'a'/'cp2_dashboard.html').read_text(encoding='utf-8')


def test_evidence_negative_scenario_rejected(tmp_path):
    with pytest.raises(ValueError, match='quality gate'):
        build_cp2_evidence(scenario='contaminated',out_dir=tmp_path/'bad')
    assert not (tmp_path/'bad'/'cp2_report.json').exists()


def test_sql_parity_detects_tampering(baseline, users):
    changed=users.copy()
    changed.loc[changed.index[0], 'sessions_7d'] += 1
    outcome=check_sql_parity(baseline, changed, DEFAULT_OBSERVATION_END)
    assert outcome['passed'] is False
    assert any(r['field']=='sessions_7d' for r in outcome['mismatches'])
