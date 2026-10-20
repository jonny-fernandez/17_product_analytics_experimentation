"""Versioned synthetic event ingestion, SQLite evidence and fail-closed analytics bridge.

Never use this toy, unauthenticated local demonstration for production traffic.
No browser/IP/person identifiers are persisted. All traffic is synthetic.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from product_analytics.data.validation import validate_event_frame
from product_analytics.metrics.product import compute_tables, make_user_metrics
from product_analytics.metrics.sql_parity import check_sql_parity
from product_analytics.schemas import EventRecord

ROOT = Path(__file__).resolve().parents[3]
TRACKING_PLAN = ROOT / "configs" / "tracking_plan_v1.json"
ID_PATTERN = re.compile(r"^(?:u|s|evt)_[a-z0-9_]{4,64}$")
UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat(timespec="microseconds")


class IngestEnvelope(BaseModel):
    """No uncontracted user attributes or event properties are accepted."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    event_id: str
    user_id: str
    session_id: str | None = None
    name: str
    source: str
    occurred_at: datetime
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_id", "user_id", "session_id")
    @classmethod
    def synthetic_ids_only(cls, value: str | None) -> str | None:
        if value is not None and not ID_PATTERN.fullmatch(value):
            raise ValueError("Only opaque synthetic IDs are permitted")
        return value

    @field_validator("occurred_at")
    @classmethod
    def strict_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must have an explicit UTC offset")
        return value.astimezone(UTC)


class EventStore:
    """One SQLite database per local demo. No background processes or cloud credentials."""

    def __init__(self, path: Path, tracking_plan: Path = TRACKING_PLAN):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.plan = json.loads(Path(tracking_plan).read_text(encoding="utf-8"))
        if self.plan.get("schema_version") != 1:
            raise ValueError("Unsupported tracking plan")
        self._setup()

    def _db(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _setup(self):
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT PRIMARY KEY, session_id TEXT UNIQUE NOT NULL,
                variant TEXT NOT NULL, channel TEXT NOT NULL, device TEXT NOT NULL,
                experiment_id TEXT NOT NULL, consent INTEGER NOT NULL CHECK (consent=1)
            );
            CREATE TABLE IF NOT EXISTS accepted (
                event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, session_id TEXT,
                name TEXT NOT NULL, source TEXT NOT NULL,
                occurred_at TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
                canonical_json TEXT NOT NULL, received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_accepted_user ON accepted(user_id, occurred_at);
            CREATE TABLE IF NOT EXISTS quarantine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL, event_id TEXT, observed_at TEXT NOT NULL
            );
            """)

    def add_session(self, *, user_id: str, session_id: str, consent: bool,
                    variant: str = "A", channel: str = "direct", device: str = "desktop") -> None:
        if not consent:
            raise ValueError("Consent required before starting an instrumented session")
        if not ID_PATTERN.fullmatch(user_id) or not ID_PATTERN.fullmatch(session_id):
            raise ValueError("Only opaque synthetic IDs are permitted")
        if variant not in ("A", "B") or channel not in ("direct", "organic", "email", "social", "paid_search") \
                or device not in ("desktop", "mobile", "tablet"):
            raise ValueError("Invalid fixed demonstration dimensions")
        with self._db() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,1)",
                       (user_id, session_id, variant, channel, device, "local_demo"))

    def _quarantine(self, reason: str, event_id: str | None) -> dict:
        # Store code and opaque event ID only: never raw payloads or private strings.
        safe_id = event_id if isinstance(event_id, str) and ID_PATTERN.fullmatch(event_id) else None
        with self._db() as db:
            db.execute("INSERT INTO quarantine(reason,event_id,observed_at) VALUES (?,?,?)",
                       (reason, safe_id, iso(utc_now())))
        return {"status": "quarantined", "reason": reason}

    def ingest(self, incoming: dict, *, received_at: datetime | None = None) -> dict:
        """Persist a valid event, deduplicate exact retries, quarantine all other exceptions.

        Arrival order may differ from event time within 48 hours, but impossible
        chronology is rejected by the existing canonical event-quality gate.
        """
        try:
            envelope = IngestEnvelope.model_validate(incoming)
        except Exception:
            return self._quarantine("invalid_envelope", incoming.get("event_id") if isinstance(incoming, dict) else None)
        if envelope.schema_version != self.plan["schema_version"]:
            return self._quarantine("unknown_version", envelope.event_id)
        spec = self.plan["events"].get(envelope.name)
        if spec is None:
            return self._quarantine("unknown_event", envelope.event_id)
        if envelope.source != spec["source"]:
            return self._quarantine("source_mismatch", envelope.event_id)
        if set(envelope.properties) != set(spec["properties"]):
            return self._quarantine("properties_mismatch", envelope.event_id)
        revenue = envelope.properties.get("revenue", 0.0)
        if (envelope.name == "order_purchased" and (type(revenue) not in (int, float) or not 0 < revenue <= 10000)) \
                or (envelope.name != "order_purchased" and revenue != 0.0):
            return self._quarantine("revenue_invalid", envelope.event_id)
        seen_at = received_at or utc_now()
        if seen_at.tzinfo is None or seen_at.utcoffset() != timedelta(0):
            raise ValueError("received_at must be UTC")
        lag = (seen_at - envelope.occurred_at).total_seconds()
        if lag < -300:
            return self._quarantine("future_event", envelope.event_id)
        if lag > 48 * 3600:
            return self._quarantine("too_late", envelope.event_id)
        content = envelope.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self._db() as db:
            existing = db.execute("SELECT payload_sha256 FROM accepted WHERE event_id=?", (envelope.event_id,)).fetchone()
            if existing is not None:
                if existing["payload_sha256"] == digest:
                    return {"status": "duplicate", "event_id": envelope.event_id}
                return self._quarantine("id_conflict", envelope.event_id)
            context = db.execute("SELECT * FROM sessions WHERE user_id=?", (envelope.user_id,)).fetchone()
            if context is None:
                return self._quarantine("unknown_actor", envelope.event_id)
            if envelope.session_id != (None if envelope.name == "experiment_assigned" else context["session_id"]):
                return self._quarantine("session_mismatch", envelope.event_id)
            canonical = dict(event_id=envelope.event_id, user_id=envelope.user_id,
                             session_id=envelope.session_id, event_timestamp=envelope.occurred_at,
                             event_name=spec["canonical"], page="product" if spec["canonical"] == "view_item" else None,
                             channel=context["channel"], campaign=None, device=context["device"],
                             experiment_id=context["experiment_id"], variant=context["variant"],
                             conversion=1 if envelope.name == "order_purchased" else 0,
                             revenue=float(revenue))
            try:
                canonical = EventRecord.model_validate(canonical).model_dump(mode="json")
            except Exception:
                return self._quarantine("canonical_contract", envelope.event_id)
            # Accept every unique event, but do not assert full-session correctness until gate evaluation.
            inserted = db.execute("INSERT OR IGNORE INTO accepted VALUES (?,?,?,?,?,?,?,?,?)",
                                  (envelope.event_id, envelope.user_id, envelope.session_id, envelope.name,
                                   envelope.source, iso(envelope.occurred_at), digest,
                                   json.dumps(canonical, sort_keys=True), iso(seen_at))).rowcount == 1
            current_digest = (db.execute("SELECT payload_sha256 FROM accepted WHERE event_id=?",
                                         (envelope.event_id,)).fetchone()["payload_sha256"] if not inserted else None)
        if not inserted:
            if current_digest == digest:
                return {"status": "duplicate", "event_id": envelope.event_id}
            return self._quarantine("id_conflict", envelope.event_id)
        return {"status": "accepted", "event_id": envelope.event_id}

    def frame(self) -> pd.DataFrame:
        with self._db() as db:
            rows = db.execute("SELECT canonical_json FROM accepted ORDER BY occurred_at,event_id").fetchall()
        values = [json.loads(row["canonical_json"]) for row in rows]
        if not values:
            return pd.DataFrame(columns=list(EventRecord.model_fields))
        for value in values:
            value["event_timestamp"] = datetime.fromisoformat(value["event_timestamp"])
        return pd.DataFrame(values)[list(EventRecord.model_fields)]

    def monitor(self, *, received_at: datetime | None = None, min_events: int = 1,
                baseline_hourly_events: int | None = None) -> dict:
        now = received_at or utc_now()
        with self._db() as db:
            accepted = [dict(r) for r in db.execute("SELECT received_at,occurred_at,name FROM accepted")]
            rejected = [r["reason"] for r in db.execute("SELECT reason FROM quarantine")]
        quality = validate_event_frame(self.frame())
        lag_sec = [max(0.0, (datetime.fromisoformat(r["received_at"]) - datetime.fromisoformat(r["occurred_at"])).total_seconds()) for r in accepted]
        alerts = []
        if not quality["valid"]:
            alerts.append("CANONICAL_QUALITY_GATE_FAILED")
        if len(accepted) < min_events:
            alerts.append("VOLUME_BELOW_MINIMUM")
        if rejected:
            alerts.append("QUARANTINED_EVENT_ATTEMPTS")
        if any(lag > 300 for lag in lag_sec):
            alerts.append("INGESTION_LAG_ABOVE_300_SECONDS")
        # Approximate recent volume check, not a learned anomaly detector.
        last_hour = sum(0 <= (now - datetime.fromisoformat(r["received_at"])).total_seconds() <= 3600
                        for r in accepted)
        if baseline_hourly_events is not None:
            if not isinstance(baseline_hourly_events, int) or baseline_hourly_events < 1:
                raise ValueError("baseline_hourly_events must be a positive integer")
            if last_hour < .5 * baseline_hourly_events or last_hour > 1.5 * baseline_hourly_events:
                alerts.append("VOLUME_DRIFT_OVER_50_PERCENT")
        return {"accepted_events": len(accepted), "last_hour_events": last_hour,
                "quarantined_attempts": len(rejected), "quarantine_codes": dict(sorted(Counter(rejected).items())),
                "max_ingestion_lag_seconds": round(max(lag_sec, default=0.0), 3),
                "quality": quality, "alerts": alerts, "passed": not alerts}

    def governed_metrics(self, *, observation_end: datetime | None = None) -> dict:
        """No 7-day KPIs released without valid full event chronology and mature windows."""
        frame = self.frame()
        quality = validate_event_frame(frame)
        if self.monitor()["quarantined_attempts"]:
            return {"status": "BLOCK", "reason": "QUARANTINED_EVENT_ATTEMPTS", "quality": quality}
        if not quality["valid"]:
            return {"status": "BLOCK", "reason": "EVENT_QUALITY", "quality": quality}
        if frame.empty:
            return {"status": "BLOCK", "reason": "NO_EVENTS", "quality": quality}
        end = observation_end or utc_now()
        try:
            users = make_user_metrics(frame, observation_end=end)
            if len(users) != quality["unique_users"]:
                return {"status": "BLOCK", "reason": "INCOMPLETE_7_DAY_WINDOW", "eligible": len(users),
                        "users": quality["unique_users"]}
            metrics = compute_tables(users, observation_end=end)
            parity = check_sql_parity(frame, users, observation_end=end)
            if not parity["passed"]:
                return {"status": "BLOCK", "reason": "SQL_PARITY", "parity": parity}
        except Exception as exc:
            return {"status": "BLOCK", "reason": "METRIC_COMPUTATION", "error_type": type(exc).__name__}
        return {"status": "PASS", "source": "synthetic_local_event_ingestion", "metrics": metrics,
                "sql_parity": parity, "quality": quality}
