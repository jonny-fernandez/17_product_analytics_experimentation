"""Deterministic synthetic product journeys; no production or customer data."""

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd

SCENARIOS = {
    # CP1 fixtures, not inference or observations. MDE in config is 5% relative.
    "baseline": {"a": 0.10, "b": 0.105, "allocation_b": 0.50, "expected_valid": True},
    "null": {"a": 0.10, "b": 0.10, "allocation_b": 0.50, "expected_valid": True},
    "positive": {"a": 0.10, "b": 0.13, "allocation_b": 0.50, "expected_valid": True},
    "underpowered": {"a": 0.10, "b": 0.105, "allocation_b": 0.50, "expected_valid": True},
    "srm": {"a": 0.10, "b": 0.105, "allocation_b": 0.80, "expected_valid": True},
    "contaminated": {"a": 0.10, "b": 0.105, "allocation_b": 0.50, "expected_valid": False},
    "invalid_event": {"a": 0.10, "b": 0.105, "allocation_b": 0.50, "expected_valid": False},
}


def generate_events(n_users: int = 500, seed: int = 42, scenario: str = "baseline") -> pd.DataFrame:
    """Generate events with stable user assignments and ordered, sometimes repeated sessions.

    Data contain only synthetic identifiers. The underpowered fixture is capped at 60 users
    because it represents a small-sample example, not an experiment recommendation.
    """
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; expected {sorted(SCENARIOS)}")
    if not isinstance(n_users, int) or isinstance(n_users, bool) or not 1 <= n_users <= 200_000:
        raise ValueError("n_users must be an integer between 1 and 200000")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if scenario == "underpowered" and n_users > 60:
        raise ValueError("underpowered scenario is limited to 60 users")

    cfg = SCENARIOS[scenario]
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc)
    channels = ["organic", "paid_search", "email", "direct", "social"]
    devices = ["mobile", "desktop", "tablet"]

    def add_event(user_id, session_id, when, event_name, variant, channel, device,
                  page=None, campaign=None, conversion=0, revenue=0.0):
        rows.append({
            "event_id": f"e{len(rows) + 1:09d}", "user_id": user_id,
            "session_id": session_id, "event_timestamp": when, "event_name": event_name,
            "page": page, "channel": channel, "campaign": campaign,
            "device": device, "experiment_id": "landing_page_test", "variant": variant,
            "conversion": conversion, "revenue": revenue,
        })

    for i in range(n_users):
        user = f"u{i:06d}"
        variant = "B" if rng.random() < cfg["allocation_b"] else "A"
        device = str(rng.choice(devices))
        channel = str(rng.choice(channels))
        campaign = "synthetic_launch" if channel in ("paid_search", "email") else None
        t0 = origin + timedelta(minutes=int(rng.integers(0, 60 * 24 * 30)))
        sid = f"s{i:06d}_0"
        add_event(user, None, t0 - timedelta(seconds=2), "experiment_assignment", variant,
                  channel, device, campaign=campaign)
        add_event(user, sid, t0, "session_start", variant, channel, device, "landing", campaign)
        add_event(user, sid, t0 + timedelta(seconds=10), "experiment_exposure", variant,
                  channel, device, "landing", campaign)
        # Funnel designed so expected overall conversion is near the given rate;
        # realized conversion is stochastic, with no promise of a positive result.
        viewed = rng.random() < 0.80
        added = viewed and rng.random() < 0.65
        checkout = added and rng.random() < 0.55
        bought = checkout and rng.random() < (cfg[variant.lower()] / (0.80 * 0.65 * 0.55))
        if viewed:
            add_event(user, sid, t0 + timedelta(seconds=20), "view_item", variant,
                      channel, device, "product", campaign)
        if added:
            add_event(user, sid, t0 + timedelta(seconds=30), "add_to_cart", variant,
                      channel, device, "cart", campaign)
        if checkout:
            add_event(user, sid, t0 + timedelta(seconds=40), "begin_checkout", variant,
                      channel, device, "checkout", campaign)
        if bought:
            add_event(user, sid, t0 + timedelta(seconds=50), "purchase", variant,
                      channel, device, "confirmation", campaign,
                      conversion=1, revenue=float(rng.integers(25, 200)))
        if rng.random() < 0.025:
            add_event(user, sid, t0 + timedelta(seconds=60), "error", variant,
                      channel, device, "error", campaign)
        if rng.random() < 0.25:
            day_offset = int(rng.integers(1, 7))
            return_time = t0 + timedelta(days=day_offset)
            return_channel = str(rng.choice(channels))
            return_campaign = "synthetic_retargeting" if return_channel == "email" else None
            sid2 = f"s{i:06d}_1"
            add_event(user, sid2, return_time, "session_start", variant,
                      return_channel, device, "landing", return_campaign)
            if rng.random() < 0.85:
                add_event(user, sid2, return_time + timedelta(seconds=20), "view_item", variant,
                          return_channel, device, "product", return_campaign)

    if scenario == "contaminated":
        rows.append(dict(rows[0]))  # duplicated event ID
        conflict = dict(rows[0])
        conflict.update({"event_id": f"e{len(rows)+1:09d}",
                         "variant": "A" if rows[0]["variant"] == "B" else "B"})
        rows.append(conflict)  # double assignment to one user
    if scenario == "invalid_event":
        bad = dict(rows[1])  # session_start user with no preceding checkout
        bad.update({"event_id": f"e{len(rows)+1:09d}", "event_name": "purchase",
                    "event_timestamp": bad["event_timestamp"] + timedelta(seconds=3),
                    "conversion": 1, "revenue": -20.0})
        rows.append(bad)

    return pd.DataFrame(rows)
