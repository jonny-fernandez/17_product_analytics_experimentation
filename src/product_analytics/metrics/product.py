"""Offline descriptive product metrics. No experiment hypothesis testing or causal inference."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from product_analytics.data.validation import validate_event_frame

UTC = timezone.utc
DEFAULT_OBSERVATION_END = datetime(2026, 2, 9, tzinfo=UTC)
FUNNEL_STEPS = ("session_start", "view_item", "add_to_cart", "begin_checkout", "purchase")


def _iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat(timespec="seconds")


def _rate(n: int | float, d: int | float) -> float | None:
    return None if d <= 0 else float(n / d)


def make_user_metrics(frame: pd.DataFrame, observation_end: datetime = DEFAULT_OBSERVATION_END) -> pd.DataFrame:
    """Return one row per eligible exposed user; reject all invalid input before analysis.

    Eligibility is first exposure + fully declared 7-day observation horizon.
    Only synthetic/authorized event data belong in this offline portfolio system.
    """
    if not isinstance(observation_end, datetime) or observation_end.utcoffset() != timedelta(0):
        raise ValueError("observation_end must be UTC-aware")
    report = validate_event_frame(frame)
    if not report["valid"]:
        raise ValueError(f"Event-quality gate failed: {report['error_codes']}")
    if frame.empty:
        raise ValueError("No events supplied")
    events = frame.copy()
    events["event_timestamp"] = pd.to_datetime(events["event_timestamp"], utc=True)
    events = events.sort_values(["event_timestamp", "event_id"], kind="stable")
    assignments = events[events.event_name == "experiment_assignment"].set_index("user_id")
    exposures = events[events.event_name == "experiment_exposure"].set_index("user_id")
    starts = events[events.event_name == "session_start"]
    all_sessions = {user: group.sort_values("event_timestamp").to_dict("records") for user, group in starts.groupby("user_id")}
    user_events = {user: group.to_dict("records") for user, group in events.groupby("user_id")}
    out = []
    for user, assignment in assignments.iterrows():
        exposure = exposures.loc[user]
        exp_ts = exposure.event_timestamp.to_pydatetime()
        window_end = exp_ts + timedelta(days=7)
        if observation_end < window_end:
            continue
        sessions = all_sessions[user]
        first = sessions[0]
        first_start_ts = first["event_timestamp"].to_pydatetime()
        first_sid = first["session_id"]
        first_channel = first["channel"]
        user_rows = user_events[user]
        first_session = [r for r in user_rows if r["session_id"] == first_sid]
        prior = first_start_ts
        step_flags = {"session_start": 1}
        for step in FUNNEL_STEPS[1:]:
            # First shopping step must be after exposure; all later steps after prior step.
            threshold = max(prior, exp_ts) if step == "view_item" else prior
            candidates = [r for r in first_session if r["event_name"] == step
                          and threshold < r["event_timestamp"].to_pydatetime() < window_end]
            if candidates and step_flags[FUNNEL_STEPS[FUNNEL_STEPS.index(step)-1]]:
                prior = min(r["event_timestamp"].to_pydatetime() for r in candidates)
                step_flags[step] = 1
            else:
                step_flags[step] = 0
        window_events = [r for r in user_rows if exp_ts <= r["event_timestamp"].to_pydatetime() < window_end]
        purchases = [r for r in window_events if r["event_name"] == "purchase"]
        return_sessions = [r for r in sessions if r["event_timestamp"].to_pydatetime() > first_start_ts
                           and r["event_timestamp"].to_pydatetime() < window_end]
        day_returns = {
            f"d{day}_return": int(any((r["event_timestamp"].date() - first["event_timestamp"].date()).days == day
                                      for r in return_sessions))
            for day in range(1, 8)
        }
        # Cohort date is the first session's UTC calendar date; no assignment-based selection.
        observed_touches = [r["channel"] for r in sessions if first_start_ts <= r["event_timestamp"].to_pydatetime() < window_end]
        out.append({
            "user_id": user, "variant": assignment.variant, "device": assignment.device,
            "channel": first_channel, "cohort_day": str(first["event_timestamp"].date()),
            "exposure_ts": _iso(exp_ts), "first_start_ts": _iso(first_start_ts),
            "purchased_7d": int(bool(purchases)), "revenue_7d": float(sum(r["revenue"] for r in purchases)),
            "error_7d": int(any(r["event_name"] == "error" for r in window_events)),
            "bounce_first_session": int(not any(r["event_name"] == "view_item" for r in first_session)),
            "sessions_7d": 1 + len(return_sessions),
            "first_touch": observed_touches[0], "last_touch": observed_touches[-1],
            "touches": tuple(observed_touches),
            **{f"funnel_{step}": flag for step, flag in step_flags.items()},
            **day_returns,
        })
    return pd.DataFrame(out)


def compute_tables(users: pd.DataFrame, observation_end: datetime = DEFAULT_OBSERVATION_END) -> dict[str, Any]:
    """Tabular descriptive results, explicit nulls for zero denominators and immature cohorts."""
    if users.empty:
        raise ValueError("No fully observed exposed users for the declared observation end")
    n = len(users)
    buyers = int(users.purchased_7d.sum())
    summary = {
        "eligible_exposed_users": n,
        "purchasing_users_7d": buyers,
        "purchase_conversion_7d": _rate(buyers, n),
        "total_revenue_7d": float(users.revenue_7d.sum()),
        "revenue_per_exposed_user": float(users.revenue_7d.sum() / n),
        "users_with_errors_7d": int(users.error_7d.sum()),
        "error_incidence_7d": float(users.error_7d.mean()),
        "bounce_first_session": float(users.bounce_first_session.mean()),
        "sessions_7d": int(users.sessions_7d.sum()),
        "repeat_session_users_7d": int((users.sessions_7d > 1).sum()),
    }
    funnel = []
    prev = n
    for step in FUNNEL_STEPS:
        count = int(users[f"funnel_{step}"].sum())
        funnel.append({"step": step, "users": count, "from_eligible": _rate(count, n),
                       "from_previous": _rate(count, prev), "dropoff_from_previous": None if prev == 0 else 1-count/prev})
        prev = count
    retention = []
    for cohort, group in users.groupby("cohort_day", sort=True):
        cohort_date = datetime.fromisoformat(cohort).replace(tzinfo=UTC)
        for day in range(1, 8):
            matured = cohort_date + timedelta(days=day+1) <= observation_end
            retained = int(group[f"d{day}_return"].sum()) if matured else None
            retention.append({"cohort_day": cohort, "day": day, "cohort_users": len(group),
                              "eligible_users": len(group) if matured else 0,
                              "returning_users": retained,
                              "retention_rate": _rate(retained, len(group)) if matured else None})
    segments = []
    for dimension in ("channel", "device"):
        for value, group in users.groupby(dimension, sort=True):
            segments.append({"dimension": dimension, "value": value,
                             "users": len(group), "purchasing_users": int(group.purchased_7d.sum()),
                             "purchase_rate": _rate(int(group.purchased_7d.sum()), len(group)),
                             "revenue": float(group.revenue_7d.sum())})
    credits: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for u in users.itertuples(index=False):
        if not u.purchased_7d:
            continue
        for model, touches in (("first_touch", (u.first_touch,)),
                               ("last_touch", (u.last_touch,)),
                               ("linear_multitouch", u.touches)):
            weight = 1.0 / len(touches)
            for channel in touches:
                credits[(model, channel)][0] += weight
                credits[(model, channel)][1] += weight * u.revenue_7d
    attribution = [{"model": model, "channel": channel, "buyer_credit": round(credit[0], 9),
                    "revenue_credit": round(credit[1], 9)}
                   for (model, channel), credit in sorted(credits.items())]
    journeys = {
        "users": n,
        "sessions": int(users.sessions_7d.sum()),
        "avg_sessions_per_user": float(users.sessions_7d.mean()),
        "repeat_session_users": int((users.sessions_7d > 1).sum()),
        "multichannel_users": int(sum(len(set(t)) > 1 for t in users.touches)),
    }
    return {"summary": summary, "funnel": funnel, "retention": retention,
            "segments": segments, "attribution": attribution, "journeys": journeys}
