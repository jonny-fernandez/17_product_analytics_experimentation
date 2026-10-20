r"""Run offline CP3 quality gates and package evidence; does not modify Git.

Usage (from the CP2 working repo on Windows):
    .\.venv\Scripts\python.exe scripts\project17_cp3_quality_evidence.py
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
EVIDENCE = ROOT / "artifacts" / f"cp3_quality_{STAMP}"
ZIP_PATH = ROOT / "artifacts" / f"Project17_CP3_Evidence_{STAMP}.zip"


def run_step(label: str, command: list[str], timeout: int = 1800) -> bool:
    out = EVIDENCE / f"{label}.stdout.txt"
    err = EVIDENCE / f"{label}.stderr.txt"
    print(f"[{label}] Executing...", flush=True)
    try:
        with out.open("w", encoding="utf-8") as stdout, err.open("w", encoding="utf-8") as stderr:
            completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                       timeout=timeout, check=False)
        ok = completed.returncode == 0
        print(f"[{label}] {'PASS' if ok else 'FAIL'} (exit {completed.returncode})", flush=True)
        tail = out.read_text(encoding="utf-8", errors="replace").splitlines()[-6:]
        if tail:
            print("\n".join(tail), flush=True)
        if not ok:
            print("Review:", out, err, flush=True)
        return ok
    except (OSError, subprocess.TimeoutExpired) as exc:
        (EVIDENCE / f"{label}.runner_error.txt").write_text(
            f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        print(f"[{label}] FAIL: {type(exc).__name__}", flush=True)
        return False


def verify_one(folder: Path) -> tuple[bool, dict, str]:
    try:
        f = folder / "instrumentation_report.json"
        saved = f.read_bytes()
        manifest = (folder / "instrumentation_report.sha256").read_text(encoding="utf-8").split()
        actual = hashlib.sha256(saved).hexdigest()
        report = json.loads(saved)
        good = (
            len(manifest) == 2 and manifest[0] == actual
            and manifest[1] == "instrumentation_report.json"
            and report.get("governed", {}).get("status") == "PASS"
            and report.get("governed", {}).get("sql_parity", {}).get("passed") is True
            and report.get("monitor", {}).get("passed") is True
            and report.get("simulated_users") == 24
            and report.get("recorded_events") == 132
            and saved.endswith(b"\n") and b"\r\n" not in saved
        )
        return good, report, actual
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, {"error": f"{type(exc).__name__}: {exc}"}, ""


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=False)
    metadata = {"run_timestamp_utc": STAMP, "python": sys.version,
                "repository_path": "(operator local checkout; not embedded)",
                "note": "All event data are simulated, not product traffic."}
    git_ok = True
    for label, args in (
        ("git_head", ["git", "rev-parse", "HEAD"]),
        ("git_status", ["git", "status", "--short"]),
    ):
        git_ok = run_step(label, args, timeout=30) and git_ok
    expected_commit = "21e13ffa44470ac362d1b812c428e034ae1bd3ef"
    actual_commit = (EVIDENCE / "git_head.stdout.txt").read_text(encoding="utf-8", errors="replace").strip()
    metadata["git_head_matches_locked_baseline"] = git_ok and actual_commit == expected_commit
    print("[baseline_commit]", "PASS" if metadata["git_head_matches_locked_baseline"] else "FAIL", flush=True)
    ok_tests = run_step("full_pytest", [sys.executable, "-m", "pytest", "-o", "addopts=", "-q"])
    captured = (EVIDENCE / "full_pytest.stdout.txt").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(\d+) passed", captured)
    count = int(match.group(1)) if match else 0
    ok_tests = ok_tests and count >= 138
    metadata["full_suite_passed"] = ok_tests
    metadata["pytest_passed_count"] = count
    if count < 138:
        print("[full_pytest] Acceptance requires at least 138 passed tests.", flush=True)
    for name in ("run_a", "run_b"):
        folder = EVIDENCE / name
        ok = run_step(f"replay_{name}", [sys.executable, "-m", "product_analytics.instrumentation.demo",
                                         "--db", str(folder / "events.sqlite"),
                                         "--out-dir", str(folder), "--users", "24", "--seed", "1707"])
        metadata[f"{name}_command_passed"] = ok
    a_ok, a_data, a_hash = verify_one(EVIDENCE / "run_a")
    b_ok, b_data, b_hash = verify_one(EVIDENCE / "run_b")
    identical = (a_ok and b_ok and a_hash == b_hash and
                 (EVIDENCE / "run_a" / "instrumentation_report.json").read_bytes() ==
                 (EVIDENCE / "run_b" / "instrumentation_report.json").read_bytes())
    metadata.update({"first_report_sha256_valid": a_ok, "second_report_sha256_valid": b_ok,
                     "two_replays_identical": identical,
                     "recorded_events": a_data.get("recorded_events"),
                     "sql_parity_passed": a_data.get("governed", {}).get("sql_parity", {}).get("passed")})
    print("[digest]", "PASS" if identical else "FAIL", flush=True)
    audit_path = EVIDENCE / "source_tree_audit.json"
    audit_command_ok = run_step("source_audit", [sys.executable, "-m", "product_analytics.audit.cp4_audit",
                                                  "--out", str(audit_path)])
    try:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit_ok = audit_command_ok and audit.get("passed") is True
    except (ValueError, OSError):
        audit_ok = False
    metadata["source_audit_passed"] = audit_ok
    metadata["git_index_note"] = "Index not re-staged or changed; audit covers the current source tree only."
    success = all((ok_tests, identical, audit_ok, metadata["git_head_matches_locked_baseline"],
                   metadata.get("run_a_command_passed"), metadata.get("run_b_command_passed")))
    metadata["overall"] = "PASS" if success else "FAIL"
    (EVIDENCE / "cp3_quality_summary.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    # Exclude generated SQLite files from the ZIP; the deterministic, hashed JSON
    # reports are enough to review quality, and are small to upload.
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(EVIDENCE.rglob("*")):
            if p.is_file() and p.suffix not in {".sqlite", ".db"}:
                z.write(p, arcname=p.relative_to(EVIDENCE).as_posix())
    print(json.dumps({"cp3_status": metadata["overall"], "pytest_passed_count": count,
                      "sha256_verified": identical, "source_audit_passed": audit_ok,
                      "evidence_zip": str(ZIP_PATH)}, indent=2), flush=True)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
