"""CP2 additive synthetic instrumentation / governed metric gate regression suite."""
from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from product_analytics.instrumentation.core import EventStore, iso
from product_analytics.instrumentation.demo import NAMES, replay
from product_analytics.instrumentation.webapp import create_handler

T0 = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)


def envelope(name, idx=0, *, occurred_at=None, **replace):
    fields = {"schema_version": 1, "event_id": f"evt_0000{idx:04d}",
              "user_id": "u_00000001", "session_id": None if name == "experiment_assigned" else "s_00000001",
              "name": name, "source": "client" if name in NAMES[3:6] else "server",
              "occurred_at": iso(occurred_at or T0 + timedelta(seconds=idx * 2)),
              "properties": {"revenue": 45.0} if name == "order_purchased" else {}}
    fields.update(replace)
    return fields


@pytest.fixture
def store(tmp_path):
    thing = EventStore(tmp_path / "events.sqlite")
    thing.add_session(user_id="u_00000001", session_id="s_00000001", consent=True)
    return thing


def submit(store, payload, lag=1):
    return store.ingest(payload, received_at=datetime.fromisoformat(payload["occurred_at"]) + timedelta(seconds=lag))


def journey(store, *, purchased=True):
    names = NAMES if purchased else NAMES[:4]
    return [submit(store, envelope(name, i)) for i, name in enumerate(names)]


def test_exact_tracking_plan_and_expected_mapping(store):
    assert store.plan["schema_version"] == 1
    assert {spec["source"] for spec in store.plan["events"].values()} == {"server", "client"}
    assert all("_" in name and name.islower() for name in store.plan["events"])
    assert set(store.plan["events"]) == set(NAMES)


def test_positive_synthetic_full_journey_python_sql_parity(store):
    assert all(x["status"] == "accepted" for x in journey(store))
    result = store.governed_metrics(observation_end=T0 + timedelta(days=12))
    assert result["status"] == "PASS", result
    assert result["sql_parity"]["passed"]
    assert result["sql_parity"]["compared_user_fields"] == 25
    assert result["metrics"]["summary"]["purchasing_users_7d"] == 1
    assert result["metrics"]["summary"]["total_revenue_7d"] == 45


def test_incomplete_seven_day_window_blocks(store):
    journey(store)
    result = store.governed_metrics(observation_end=T0 + timedelta(days=3))
    assert result["status"] == "BLOCK"
    assert result["reason"] == "INCOMPLETE_7_DAY_WINDOW"


def test_nonpurchase_user_does_not_create_fictitious_conversions(store):
    journey(store, purchased=False)
    result = store.governed_metrics(observation_end=T0 + timedelta(days=12))
    assert result["status"] == "PASS", result
    assert result["metrics"]["summary"]["purchasing_users_7d"] == 0


def test_consent_required_before_session(tmp_path):
    store = EventStore(tmp_path / "events.sqlite")
    with pytest.raises(ValueError, match="Consent"):
        store.add_session(user_id="u_00000001", session_id="s_00000001", consent=False)


@pytest.mark.parametrize("change,code", [
    ({"schema_version": 2}, "unknown_version"),
    ({"name": "card_viewed"}, "unknown_event"),
    ({"source": "server"}, "source_mismatch"),
    ({"properties": {"email": "sample@example.com"}}, "properties_mismatch"),
    ({"user_id": "alice@example.com"}, "invalid_envelope"),
    ({"session_id": "s_anotherperson"}, "session_mismatch"),
    ({"occurred_at": "2026-01-10T12:00:00"}, "invalid_envelope"),
    ({"source": "client", "name": "order_purchased", "properties": {"revenue": 45.0}}, "source_mismatch"),
    ({"unexpected": "surveillance"}, "invalid_envelope"),
])
def test_negative_contract_cases_quarantine(store, change, code):
    value = envelope("product_viewed", 1)
    value.update(change)
    got = submit(store, value) if "occurred_at" not in change else store.ingest(value, received_at=T0 + timedelta(seconds=4))
    assert got == {"status": "quarantined", "reason": code}
    assert store.monitor()["quarantine_codes"][code] == 1
    assert store.governed_metrics()["status"] == "BLOCK"


def test_replay_exact_duplicate_and_conflicting_id(store):
    ev = envelope("experiment_assigned", 0)
    assert submit(store, ev)["status"] == "accepted"
    assert submit(store, ev)["status"] == "duplicate"
    conflicting = {**ev, "occurred_at": iso(T0 + timedelta(seconds=10))}
    assert submit(store, conflicting)["reason"] == "id_conflict"
    assert len(store.frame()) == 1


def test_future_and_too_late_events_quarantine(store):
    event = envelope("experiment_assigned", 0)
    assert store.ingest(event, received_at=T0 - timedelta(minutes=6))["reason"] == "future_event"
    assert store.ingest(event, received_at=T0 + timedelta(hours=49))["reason"] == "too_late"
    assert store.frame().empty


def test_negative_revenue_nan_and_string(store):
    for i, revenue in enumerate((-1, float("nan"), "20", True), 1):
        event = envelope("order_purchased", i, properties={"revenue": revenue})
        assert submit(store, event)["reason"] == "revenue_invalid"


def test_gate_detects_incomplete_and_disordered_funnel(store):
    assert submit(store, envelope("experiment_assigned", 0))["status"] == "accepted"
    assert submit(store, envelope("session_started", 1))["status"] == "accepted"
    assert submit(store, envelope("experiment_exposed", 2))["status"] == "accepted"
    # Purchase event contract is syntactically valid, but canonical order is not.
    assert submit(store, envelope("order_purchased", 6))["status"] == "accepted"
    result = store.governed_metrics(observation_end=T0 + timedelta(days=12))
    assert result["status"] == "BLOCK" and result["reason"] == "EVENT_QUALITY"


def test_arrival_out_of_order_but_valid_event_time(store):
    events = [envelope(name, i) for i, name in enumerate(NAMES)]
    # Later property-view event arrives after cart, even though occurred first.
    for i in (0, 1, 2, 4, 3, 5, 6):
        assert store.ingest(events[i], received_at=T0 + timedelta(seconds=30 + i))["status"] == "accepted"
    assert store.governed_metrics(observation_end=T0 + timedelta(days=12))["status"] == "PASS"


def test_monitor_lag_and_volume_drift_and_quarantine(store):
    assert store.monitor(min_events=3)["alerts"] == ["VOLUME_BELOW_MINIMUM"]
    journey(store)
    report = store.monitor(received_at=T0 + timedelta(minutes=20), baseline_hourly_events=40)
    assert "VOLUME_DRIFT_OVER_50_PERCENT" in report["alerts"]
    late = envelope("product_viewed", 50, occurred_at=T0 + timedelta(minutes=50))
    assert store.ingest(late, received_at=T0 + timedelta(minutes=60))["status"] == "accepted"
    assert "INGESTION_LAG_ABOVE_300_SECONDS" in store.monitor()["alerts"]
    with pytest.raises(ValueError):
        store.monitor(baseline_hourly_events=0)


def test_replay_complete_written_evidence_and_digest(tmp_path):
    out = tmp_path / "report"
    result = replay(path=tmp_path / "synthetic.sqlite", out_dir=out, users=24, seed=1707)
    assert result["governed"]["status"] == "PASS"
    assert result["governed"]["sql_parity"]["passed"] is True
    assert result["monitor"]["passed"] is True
    assert (out / "instrumentation_dashboard.html").is_file()
    assert (out / "instrumentation_report.sha256").is_file()
    assert json.loads((out / "instrumentation_report.json").read_text())["seed"] == 1707
    with pytest.raises(FileExistsError):
        replay(path=tmp_path / "synthetic.sqlite", out_dir=out)


def test_legacy_event_schema_unchanged(store):
    journey(store)
    assert set(store.frame().columns) == set(__import__("product_analytics.schemas", fromlist=["EventRecord"]).EventRecord.model_fields)


def test_no_raw_payload_persisted_in_quarantine(store):
    suspicious = envelope("product_viewed", 1, properties={"email": "somebody@private.example"})
    submit(store, suspicious)
    with sqlite3.connect(store.path) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(quarantine)")}
        assert columns == {"id", "reason", "event_id", "observed_at"}
        assert not any("somebody" in str(row) for row in db.execute("SELECT * FROM quarantine"))


def test_webapp_http_handler_is_constructor_only(store):
    handler = create_handler(store)
    assert hasattr(handler, "do_GET") and hasattr(handler, "do_POST")


def test_real_loopback_http_workflow(tmp_path):
    """Exercise a real local HTTP listener; no Internet access or analytics credentials."""
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer
    from threading import Thread
    from uuid import uuid4
    from datetime import datetime, timezone
    from time import sleep

    store = EventStore(tmp_path / "web.sqlite")
    server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(store))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        def request(method, url, payload=None):
            conn = HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            body = None if payload is None else json.dumps(payload).encode()
            conn.request(method, url, body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            out = (response.status, response.read().decode())
            conn.close()
            return out
        assert request("GET", "/health")[0] == 200
        assert request("GET", "/app.js")[0] == 200
        assert request("POST", "/api/start", {"consent": False})[0] == 403
        status, payload = request("POST", "/api/start", {"consent": True})
        assert status == 200
        session = json.loads(payload)
        assert session["tracking_version"] == 1
        assert request("POST", "/api/purchase", {"user_id": session["user_id"],
                                                       "session_id": session["session_id"]})[0] == 409
        assert request("POST", "/api/event", {"name": "order_purchased"})[0] == 403
        for name in ("product_viewed", "cart_item_added", "checkout_started"):
            sleep(.012)
            event = {"schema_version": 1, "event_id": "evt_" + uuid4().hex,
                     "user_id": session["user_id"], "session_id": session["session_id"],
                     "name": name, "occurred_at": datetime.now(timezone.utc).isoformat(),
                     "properties": {}}
            code, response = request("POST", "/api/event", event)
            assert code == 200, response
        code, response = request("POST", "/api/purchase", {"user_id": session["user_id"],
                                                        "session_id": session["session_id"]})
        assert code == 200, response
        status, report = request("GET", "/api/status")
        assert status == 200
        data = json.loads(report)
        assert data["monitor"]["quality"]["valid"] is True
        assert data["release"] == "BLOCK" and data["reason"] == "INCOMPLETE_7_DAY_WINDOW"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
