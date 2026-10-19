"""CP1 evidence generator. Offline-only; reports synthetic fixtures, not A/B outcomes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from product_analytics.data.synthetic_events import SCENARIOS, generate_events
from product_analytics.data.validation import validate_event_frame


def build_evidence(scenario: str, n_users: int, seed: int, out_dir: Path) -> dict:
    frame = generate_events(n_users=n_users, seed=seed, scenario=scenario)
    validation = validate_event_frame(frame)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"cp1_{scenario}_synthetic_events.csv"
    frame.to_csv(csv_path, index=False, lineterminator="\n")
    counts = frame.loc[frame["event_name"] == "experiment_assignment", "variant"].value_counts()
    result = {
        "checkpoint": "CP1",
        "data_classification": "deterministic synthetic fixture; not real customers, GA4, or inference",
        "scenario": scenario, "seed": seed, "requested_users": n_users,
        "assignment_counts": {k: int(counts.get(k, 0)) for k in ("A", "B")},
        "expected_valid": SCENARIOS[scenario]["expected_valid"],
        "validation": validation,
        "validation_as_expected": validation["valid"] == SCENARIOS[scenario]["expected_valid"],
        "csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
        "csv_filename": csv_path.name,
        "statistical_inference_performed": False,
    }
    report_path = out_dir / f"cp1_{scenario}_report.json"
    report_path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Create offline CP1 synthetic evidence")
    p.add_argument("--scenario", choices=sorted(SCENARIOS), default="baseline")
    p.add_argument("--users", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", type=Path, default=Path("artifacts/cp1"))
    args = p.parse_args(argv)
    try:
        report = build_evidence(args.scenario, args.users, args.seed, args.out_dir)
    except (ValueError, OSError) as exc:
        print(f"CP1 ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["validation_as_expected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
