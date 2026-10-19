"""Event contract/quality gates; deterministic checks, no causal decisions."""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any
import pandas as pd
from pydantic import ValidationError
from product_analytics.schemas import EventRecord

REQUIRED = tuple(EventRecord.model_fields)
STEPS = ("session_start", "view_item", "add_to_cart", "begin_checkout", "purchase")


def validate_event_frame(frame: pd.DataFrame, *, max_examples: int = 20) -> dict[str, Any]:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame")
    if not isinstance(max_examples, int) or max_examples < 1:
        raise ValueError("max_examples must be >=1")
    count = Counter()
    examples = []

    def flag(code: str, message: str):
        count[code] += 1
        if len(examples) < max_examples:
            examples.append({"code": code, "detail": message})

    missing = sorted(set(REQUIRED) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(REQUIRED))
    if missing: flag("missing_columns", ", ".join(missing))
    if extra: flag("unexpected_columns", ", ".join(extra))
    if missing or extra:
        return _report(frame, count, examples, 0)

    events = []
    for index, row in enumerate(frame.to_dict("records")):
        try:
            events.append(EventRecord.model_validate(row))
        except (ValidationError, ValueError, TypeError) as exc:
            flag("schema_error", f"row {index}: {str(exc).splitlines()[0]}")
    event_ids = Counter(event.event_id for event in events)
    for event_id, n in sorted(event_ids.items()):
        if n > 1: flag("duplicate_event_id", f"event_id {event_id} appears {n} times")

    user_events = defaultdict(list)
    session_owners = defaultdict(set)
    session_meta = defaultdict(set)
    for event in events:
        user_events[event.user_id].append(event)
        if event.session_id is not None:
            session_owners[event.session_id].add(event.user_id)
            session_meta[event.session_id].add((event.channel, event.device, event.campaign))
    for session_id, owners in session_owners.items():
        if len(owners) != 1: flag("shared_session_id", f"session {session_id} has multiple users")
    for session_id, metadata in session_meta.items():
        if len(metadata) != 1: flag("session_metadata_drift", f"session {session_id} mixes attribution/device")

    for user, es in user_events.items():
        es.sort(key=lambda e: (e.event_timestamp, e.event_id))
        assignments = [e for e in es if e.event_name == "experiment_assignment"]
        if len(assignments) != 1:
            flag("assignment_count", f"user {user}: expected 1 assignment, found {len(assignments)}")
            continue
        assigned = assignments[0]
        if any(e.variant != assigned.variant or e.experiment_id != assigned.experiment_id for e in es):
            flag("assignment_mismatch", f"user {user} has variant/experiment disagreement")
        other_events = [e for e in es if e.event_name != "experiment_assignment"]
        if other_events and any(e.event_timestamp <= assigned.event_timestamp for e in other_events):
            flag("preassignment_activity", f"user {user} has activity before/on assignment")
        exposures = [e for e in es if e.event_name == "experiment_exposure"]
        if len(exposures) != 1:
            flag("exposure_count", f"user {user}: expected 1 exposure, found {len(exposures)}")
        else:
            exposure = exposures[0]
            if exposure.event_timestamp <= assigned.event_timestamp:
                flag("exposure_timing", f"user {user}: exposure before assignment")
        per_session = defaultdict(list)
        for e in other_events:
            per_session[e.session_id].append(e)
        for sid, session in per_session.items():
            session.sort(key=lambda e: (e.event_timestamp, e.event_id))
            starts = [e for e in session if e.event_name == "session_start"]
            if len(starts) != 1:
                flag("session_start_count", f"user {user} session {sid}: {len(starts)} starts")
                if any(e.event_name == "purchase" for e in session):
                    flag("invalid_purchase_sequence", f"user {user} session {sid}: purchase without unique session start")
                continue
            start = starts[0].event_timestamp
            for e in session:
                if e.event_name != "session_start" and e.event_timestamp <= start:
                    flag("session_event_timing", f"user {user} session {sid}: event before start")
            for e in session:
                if e.event_name != "purchase":
                    continue
                prior = start
                for step in STEPS[1:-1]:
                    match = next((q for q in session if q.event_name == step and
                                  prior < q.event_timestamp < e.event_timestamp), None)
                    if match is None:
                        flag("invalid_purchase_sequence", f"user {user} session {sid}: missing ordered {step}")
                        break
                    prior = match.event_timestamp
                if not exposures or all(x.event_timestamp >= e.event_timestamp for x in exposures):
                    flag("purchase_before_exposure", f"user {user} session {sid}: purchase not post-exposure")
    return _report(frame, count, examples, len(events))


def _report(frame, count, examples, validated):
    return {
        "valid": not count,
        "rows": int(len(frame)),
        "schema_valid_rows": validated,
        "unique_users": int(frame["user_id"].nunique()) if "user_id" in frame else 0,
        "error_count": int(sum(count.values())),
        "error_codes": dict(sorted(count.items())),
        "examples": examples,
    }
