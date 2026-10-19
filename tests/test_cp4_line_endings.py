"""Regression protection for OS-independent, byte-locked synthetic experiment design."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from product_analytics.experimentation.cp3_analysis import DESIGN_HASH, load_locked_design

ROOT = Path(__file__).resolve().parents[1]


def test_locked_json_is_lf_only_and_matches_original_hash():
    design = ROOT / "configs/cp3_preregistered_design.json"
    raw = design.read_bytes()
    assert b"\r\n" not in raw, "Git checkout changed the locked design's bytes"
    assert sha256(raw).hexdigest() == DESIGN_HASH
    # The sidecar is a declaration, NOT an instruction to change the lock.
    expected = (ROOT / "configs/cp3_preregistered_design.sha256").read_text(encoding="utf-8").split()[0]
    assert expected == DESIGN_HASH


def test_git_attributes_protect_locked_files_on_windows_checkout():
    lines = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
    entries = {line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")}
    assert "configs/cp3_preregistered_design.json text eol=lf" in entries
    assert "configs/cp3_preregistered_design.sha256 text eol=lf" in entries


def test_crlf_tampering_still_fails_design_lock(tmp_path):
    locked = (ROOT / "configs/cp3_preregistered_design.json").read_bytes()
    changed = locked.replace(b"\n", b"\r\n")
    assert changed != locked
    simulated_windows = tmp_path / "cp3_preregistered_design.json"
    simulated_windows.write_bytes(changed)
    with pytest.raises(ValueError, match="PREREGISTRATION_MISMATCH"):
        load_locked_design(simulated_windows)
