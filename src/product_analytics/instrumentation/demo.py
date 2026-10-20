"""Seeded end-to-end ingestion replay and human-readable evidence, no network calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import random

from .core import EventStore, iso

NAMES = ("experiment_assigned", "session_started", "experiment_exposed", "product_viewed",
         "cart_item_added", "checkout_started", "order_purchased")


def replay(*, path: Path, out_dir: Path, users: int = 24, seed: int = 1707) -> dict:
    if not 2 <= users <= 200 or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Replay uses 2–200 synthetic users and a nonnegative 32-bit seed")
    if path.exists():
        # Create fresh evidence each run; avoid silently mixing distinct demo records.
        raise FileExistsError(f"Refusing to overwrite existing replay database: {path}")
    rng = random.Random(seed)
    store = EventStore(path)
    # An explicitly simulated historic event-clock allows observation windows to mature.
    origin = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    accepted = []
    for i in range(users):
        user_id, session_id = f"u_{i:08d}", f"s_{i:08d}"
        store.add_session(user_id=user_id, session_id=session_id, consent=True,
                          variant="B" if i % 2 else "A")
        purchase = rng.random() < .35
        sequence = NAMES if purchase else NAMES[:4]
        for step, name in enumerate(sequence):
            stamp = origin + timedelta(minutes=i * 20, seconds=step * 2)
            payload = {
                "schema_version": 1, "event_id": f"evt_{i:08d}_{step:02d}",
                "user_id": user_id, "session_id": None if step == 0 else session_id,
                "name": name, "source": "client" if name in NAMES[3:6] else "server",
                "occurred_at": iso(stamp),
                "properties": {"revenue": 25.0 + i} if name == "order_purchased" else {},
            }
            result = store.ingest(payload, received_at=stamp + timedelta(seconds=3))
            if result["status"] != "accepted":
                raise RuntimeError(f"Unexpected rejection in seeded replay {result}")
            accepted.append(result)
    monitor = store.monitor(received_at=origin + timedelta(days=15))
    governed = store.governed_metrics(observation_end=origin + timedelta(days=15))
    report = {
        "mode": "reproducible_local_synthetic_replay", "seed": seed,
        "simulated_users": users, "recorded_events": len(accepted),
        "tracking_plan_version": 1, "monitor": monitor, "governed": governed,
        "limitations": ["Not customer events", "No production SDK or CDP integration",
                         "Historical timestamps are simulated", "No deployment or business lift"]
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    # Hash the exact bytes committed to disk, including the final LF. Using
    # write_bytes also prevents Windows universal-newline conversion to CRLF.
    report_bytes = (data + "\n").encode("utf-8")
    (out_dir / "instrumentation_report.json").write_bytes(report_bytes)
    digest = hashlib.sha256(report_bytes).hexdigest()
    (out_dir / "instrumentation_report.sha256").write_text(digest + "  instrumentation_report.json\n", encoding="utf-8")
    state = html.escape(governed["status"])
    summary = governed.get("metrics", {}).get("summary", {})
    kpis = ''.join(f'<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>' for k,v in summary.items())
    page = f"""<!doctype html><html lang='en'><meta charset='utf-8'><title>Local instrumentation evidence</title>
<style>body{{font:16px system-ui;max-width:900px;margin:40px auto;padding:0 20px}}td,th{{padding:10px;border:1px solid #ddd;text-align:left}}table{{border-collapse:collapse}}</style>
<h1>Project 17 — synthetic instrumentation replay</h1><p>Metric release gate: <strong>{state}</strong></p>
<p>{users} simulated users, {len(accepted)} validated recorded events, seed {seed}; local SQLite source.</p>
<p>Python/SQLite parity: {html.escape(str(governed.get('sql_parity', {}).get('passed')))}</p>
<table>{kpis}</table><p>Do not interpret as real traffic or an observed experiment.</p></html>"""
    (out_dir / "instrumentation_dashboard.html").write_text(page, encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("artifacts/instrumentation_demo/events.sqlite"))
    parser.add_argument("--out-dir", type=Path, default=Path("artifacts/instrumentation_demo"))
    parser.add_argument("--users", type=int, default=24)
    parser.add_argument("--seed", type=int, default=1707)
    args = parser.parse_args(argv)
    report = replay(path=args.db, out_dir=args.out_dir, users=args.users, seed=args.seed)
    print(json.dumps({"status": report["governed"]["status"],
                      "sql_parity_passed": report["governed"].get("sql_parity", {}).get("passed"),
                      "recorded_events": report["recorded_events"],
                      "output": str(args.out_dir)}, indent=2))
    return 0 if report["governed"]["status"] == "PASS" and report["monitor"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
