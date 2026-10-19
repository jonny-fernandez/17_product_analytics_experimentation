"""CP1 schema and adversarial data quality regression tests."""
from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
from pydantic import ValidationError
from product_analytics.schemas import EventRecord
from product_analytics.data.synthetic_events import SCENARIOS, generate_events
from product_analytics.data.validation import validate_event_frame
from product_analytics.data.cp1_report import build_evidence


@pytest.fixture(scope="module")
def normal():
    return generate_events(500, seed=42)


def test_fixture_repeatable(normal):
    pd.testing.assert_frame_equal(normal, generate_events(500, seed=42))
    assert not normal.empty


def test_fixture_diverges_with_seed(normal):
    assert not normal.equals(generate_events(500, seed=43))


def test_valid_baseline(normal):
    result = validate_event_frame(normal)
    assert result["valid"], result
    assert result["unique_users"] == 500
    assert result["error_count"] == 0


def test_assignment_user_unit_and_separate_exposure(normal):
    assignments = normal[normal.event_name == "experiment_assignment"]
    exposures = normal[normal.event_name == "experiment_exposure"]
    assert len(assignments) == len(exposures) == 500
    assert assignments.user_id.is_unique
    assert assignments.session_id.isna().all()
    assert len(normal.session_id.dropna().unique()) > 500


def test_repeat_sessions_and_multitouch(normal):
    session_counts = normal[normal.event_name == "session_start"].groupby("user_id").size()
    assert session_counts.max() >= 2
    assert session_counts.min() == 1
    assert (normal.groupby("user_id").channel.nunique() > 1).any()


def test_purchase_has_ordered_ancestry(normal):
    purchases = normal[normal.event_name == "purchase"]
    assert len(purchases) > 0
    assert (purchases.revenue > 0).all()
    assert (purchases.conversion == 1).all()


def test_utc_timestamps(normal):
    assert all(value.tzinfo is not None and value.utcoffset() == timedelta(0)
               for value in normal.event_timestamp)


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_fixture_registry_detects_expected_validity(scenario):
    count = 50 if scenario == "underpowered" else 500
    result = validate_event_frame(generate_events(count, seed=42, scenario=scenario))
    assert result["valid"] is SCENARIOS[scenario]["expected_valid"], (scenario, result)


def test_srm_fixture_has_obvious_assignment_skew():
    data = generate_events(500, seed=42, scenario="srm")
    assignments = data[data.event_name == "experiment_assignment"]
    assert (assignments.variant == "B").mean() > .70
    # This is a fixture, not a statistical SRM decision; that is implemented in CP3.


def test_outcome_probabilities_distinct_from_mde():
    assert SCENARIOS["baseline"]["b"] == .105
    assert SCENARIOS["positive"]["b"] == .13


def test_duplicate_event_id_detected(normal):
    edited = pd.concat((normal, normal.iloc[[0]]), ignore_index=True)
    assert "duplicate_event_id" in validate_event_frame(edited)["error_codes"]


def test_second_conflicting_assignment_detected(normal):
    edited = pd.concat((normal, normal.iloc[[0]].copy()), ignore_index=True)
    edited.loc[edited.index[-1], "event_id"] = "e_conflict"
    edited.loc[edited.index[-1], "variant"] = "A" if normal.iloc[0].variant == "B" else "B"
    assert "assignment_count" in validate_event_frame(edited)["error_codes"]


def test_missing_exposure_detected(normal):
    frame = normal[~((normal.user_id == "u000000") & (normal.event_name == "experiment_exposure"))]
    assert "exposure_count" in validate_event_frame(frame)["error_codes"]


def test_impossible_purchase_detected(normal):
    frame = normal.copy()
    i = frame.index[(frame.event_name == "session_start")][0]
    frame.loc[i, "event_name"] = "purchase"
    frame.loc[i, "conversion"] = 1
    frame.loc[i, "revenue"] = 10.0
    assert "invalid_purchase_sequence" in validate_event_frame(frame)["error_codes"]


def test_out_of_order_steps_detected(normal):
    frame = normal.copy()
    purchase = frame[frame.event_name == "purchase"].iloc[0]
    checkout_i = frame.index[(frame.user_id == purchase.user_id) &
                             (frame.event_name == "begin_checkout")][0]
    frame.loc[checkout_i, "event_timestamp"] = purchase.event_timestamp + timedelta(minutes=1)
    assert "invalid_purchase_sequence" in validate_event_frame(frame)["error_codes"]


def test_assignment_timing_detected(normal):
    frame = normal.copy()
    i = frame.index[frame.event_name == "experiment_assignment"][0]
    frame.loc[i, "event_timestamp"] = frame.loc[i, "event_timestamp"] + timedelta(minutes=5)
    assert "preassignment_activity" in validate_event_frame(frame)["error_codes"]


def test_session_metadata_drift_detected(normal):
    frame = normal.copy()
    sid = frame.iloc[1].session_id
    i = frame.index[(frame.session_id == sid) & (frame.event_name == "experiment_exposure")][0]
    frame.loc[i, "channel"] = "email" if frame.loc[i, "channel"] != "email" else "organic"
    assert "session_metadata_drift" in validate_event_frame(frame)["error_codes"]


def test_missing_column_detected(normal):
    assert "missing_columns" in validate_event_frame(normal.drop(columns="event_id"))["error_codes"]


def test_unexpected_column_detected(normal):
    assert "unexpected_columns" in validate_event_frame(normal.assign(extra=1))["error_codes"]


def test_local_time_rejected(normal):
    bad = normal.copy()
    bad["event_timestamp"] = bad["event_timestamp"].astype(object)
    bad.at[bad.index[0], "event_timestamp"] = datetime(2026, 1, 1)  # naive
    assert "schema_error" in validate_event_frame(bad)["error_codes"]


def test_non_utc_offset_rejected(normal):
    bad = normal.iloc[0].to_dict()
    bad["event_timestamp"] = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-5)))
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_invalid_variant_rejected(normal):
    bad = normal.iloc[0].to_dict()
    bad["variant"] = "C"
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_negative_revenue_rejected(normal):
    bad = normal.iloc[0].to_dict()
    bad["revenue"] = -1
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_nonpurchase_conversion_rejected(normal):
    bad = normal.iloc[0].to_dict()
    bad["conversion"] = 1
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_blank_id_rejected(normal):
    bad = normal.iloc[0].to_dict()
    bad["user_id"] = "   "
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_missing_session_rejected(normal):
    bad = normal.iloc[1].to_dict()
    bad["session_id"] = ""
    with pytest.raises(ValidationError):
        EventRecord.model_validate(bad)


def test_generator_rejects_invalid_parameters():
    for kwargs in ({"n_users": 0}, {"n_users": -1}, {"scenario": "garbage"},
                   {"seed": -3}, {"n_users": 500, "scenario": "underpowered"}):
        with pytest.raises(ValueError):
            generate_events(**kwargs)


def test_evidence_report_is_reproducible(tmp_path):
    r1 = build_evidence("baseline", 100, 42, tmp_path / "a")
    r2 = build_evidence("baseline", 100, 42, tmp_path / "b")
    assert r1 == r2
    assert r1["validation_as_expected"] is True
    assert r1["statistical_inference_performed"] is False


def test_evidence_negative_fixture(tmp_path):
    r = build_evidence("invalid_event", 100, 42, tmp_path)
    assert r["validation"]["valid"] is False
    assert r["validation_as_expected"] is True
    assert "schema_error" in r["validation"]["error_codes"]
