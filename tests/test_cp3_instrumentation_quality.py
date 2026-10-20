"""CP3 evidence-integrity and reproducibility acceptance tests (all synthetic)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from product_analytics.instrumentation.demo import replay


def digest_record(report_dir: Path) -> tuple[str, bytes]:
    report = (report_dir / "instrumentation_report.json").read_bytes()
    expected, recorded_name = (report_dir / "instrumentation_report.sha256").read_text(
        encoding="utf-8"
    ).strip().split(maxsplit=1)
    assert recorded_name == "instrumentation_report.json"
    return expected, report


def test_saved_report_digest_matches_file_bytes_on_disk(tmp_path):
    """The CP2 bug hashed JSON without the saved LF; this catches it."""
    out = tmp_path / "report"
    replay(path=tmp_path / "db.sqlite", out_dir=out, users=24, seed=1707)
    recorded, saved = digest_record(out)
    assert saved.endswith(b"\n")
    assert not saved.endswith(b"\n\n")
    assert b"\r\n" not in saved
    assert recorded == hashlib.sha256(saved).hexdigest()
    assert json.loads(saved)["governed"]["sql_parity"]["passed"] is True


def test_report_tampering_changes_digest(tmp_path):
    out = tmp_path / "report"
    replay(path=tmp_path / "db.sqlite", out_dir=out, users=8, seed=1707)
    recorded, saved = digest_record(out)
    assert hashlib.sha256(saved).hexdigest() == recorded
    tampered = saved.replace(b'"seed": 1707', b'"seed": 1708', 1)
    assert tampered != saved
    assert hashlib.sha256(tampered).hexdigest() != recorded


def test_seeded_replays_are_report_byte_for_byte_reproducible(tmp_path):
    a = tmp_path / "report_a"
    b = tmp_path / "report_b"
    replay(path=tmp_path / "a.sqlite", out_dir=a, users=24, seed=1707)
    replay(path=tmp_path / "b.sqlite", out_dir=b, users=24, seed=1707)
    hash_a, bytes_a = digest_record(a)
    hash_b, bytes_b = digest_record(b)
    assert hash_a == hash_b
    assert bytes_a == bytes_b
    assert hash_a == hashlib.sha256(bytes_a).hexdigest()
    assert json.loads(bytes_a)["recorded_events"] == 132
