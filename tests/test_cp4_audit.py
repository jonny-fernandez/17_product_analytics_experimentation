"""CP4 negative/positive controls; no real keys or external API requests."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from product_analytics.audit.cp4_audit import (
    CASES, DESIGN_HASH, audit_evidence, audit_index, audit_tree,
    build_audit, check_content, suspicious_path,
)


def test_distributable_names_allowed():
    assert suspicious_path('.env.example') == []
    assert suspicious_path('artifacts/.gitkeep') == []
    assert suspicious_path('docs/SCREENSHOT_PLAN.md') == []


@pytest.mark.parametrize('path', [
    '.env', '.env.production', 'artifacts/private.json',
    'data/raw/events.csv', 'src/__pycache__/runtime.pyc',
    'outputs/data.json', 'credentials.json', 'key.pem',
    'models/dump.sqlite', '../outside',
])
def test_sensitive_paths_denied(path):
    assert suspicious_path(path), path


def test_no_actual_key_needed_for_negative_pattern_fixture():
    pattern = ('sk-' + 'proj-' + 'F' * 24).encode('ascii')
    result = check_content('settings.py', b'KEY=' + pattern)
    assert 'SECRET_PATTERN_openai_key' in result


def test_tree_refuses_stale_env_even_if_gitignore_would_hide_it(tmp_path):
    (tmp_path / 'safe.py').write_text('pass\n')
    assert audit_tree(tmp_path)['passed']
    (tmp_path / '.env').write_text('DO_NOT_STORE_SECRETS=1\n')
    result = audit_tree(tmp_path)
    assert not result['passed']
    assert any(f['code'] == 'SENSITIVE_FILENAME' for f in result['findings'])


def test_tree_accepts_untracked_artifact_outputs(tmp_path):
    (tmp_path / 'safe.py').write_text('pass\n')
    (tmp_path / 'artifacts').mkdir()
    (tmp_path / 'artifacts' / 'ignored.json').write_text('{}')
    assert audit_tree(tmp_path)['passed']


def _make_fixture(base: Path) -> None:
    for name, (users, seed) in CASES.items():
        target = base / f'cp3_{name}'
        target.mkdir(parents=True)
        content = f'event,scenario\ntest,{name}\n'.encode()
        (target / 'cp3_synthetic_events.csv').write_bytes(content)
        report = {
            'checkpoint': 'CP3', 'scenario': name, 'requested_users': users, 'seed': seed,
            'input_event_csv_sha256': hashlib.sha256(content).hexdigest(),
            'preregistration_sha256': DESIGN_HASH,
            'design': {'locked_design_sha256': DESIGN_HASH, 'achieved_planned_sample': False},
            'preregistration_checked_before_generation': True,
            'data_quality': {'valid': True, 'unique_users': users},
            'synthetic_data_only': True, 'live_deployment': False,
            'observed_effect_is_real_world_evidence': False,
            'release_decision': {'status': 'BLOCK_RELEASE'},
            'randomization': {'srm_failed': name == 'srm'},
        }
        (target / 'cp3_report.json').write_text(json.dumps(report), encoding='utf-8')


def test_four_case_evidence_and_negative_hash_controls(tmp_path):
    _make_fixture(tmp_path)
    assert audit_evidence(tmp_path)['passed']
    bad = tmp_path / 'cp3_srm' / 'cp3_synthetic_events.csv'
    bad.write_bytes(bad.read_bytes() + b'tampered\n')
    res = audit_evidence(tmp_path)
    assert not res['passed']
    assert any('DATA_HASH_MISMATCH' in f for f in res['findings'])


def test_evidence_missing_fails(tmp_path):
    _make_fixture(tmp_path)
    (tmp_path / 'cp3_null' / 'cp3_report.json').unlink()
    assert not audit_evidence(tmp_path)['passed']


def test_evidence_wrong_release_or_design_fails(tmp_path):
    _make_fixture(tmp_path)
    path = tmp_path / 'cp3_positive' / 'cp3_report.json'
    payload = json.loads(path.read_text())
    payload['release_decision']['status'] = 'ALLOW_RELEASE'
    payload['design']['locked_design_sha256'] = 'wrong'
    path.write_text(json.dumps(payload))
    res = audit_evidence(tmp_path)
    assert not res['passed']
    assert any('WRONG_RELEASE_DECISION' in f for f in res['findings'])
    assert any('DESIGN_LOCK_MISMATCH' in f for f in res['findings'])


def test_repository_local_design_lock_valid():
    root = Path(__file__).resolve().parents[1]
    check = build_audit(root=root, evidence_root=None, scan_index=False)
    assert check['design_lock_valid']
    assert check['tree_security']['passed']


@pytest.mark.skipif(not shutil.which('git'), reason='git executable not installed')
def test_git_index_checks_actual_staged_blob_not_worktree(tmp_path):
    def run(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    run('init', '-q')
    tracked = tmp_path / 'src.py'
    tracked.write_text('SAFE = True\n')
    run('add', 'src.py')
    assert audit_index(tmp_path)['passed']
    # Modifying an unstaged working-tree file must not affect staged audit.
    tracked.write_text('PLACEHOLDER = ' + ('sk-' + 'proj-' + 'A' * 24) + '\n')
    assert audit_index(tmp_path)['passed']
    run('add', 'src.py')
    report = audit_index(tmp_path)
    assert not report['passed']
    assert any(x['code'] == 'SECRET_PATTERN_openai_key' for x in report['findings'])
