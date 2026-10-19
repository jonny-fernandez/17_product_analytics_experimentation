"""Offline CP4 audit. No provider calls, Git writes, or credential value logging.

The staged-index check reads the actual Git INDEX, not only .gitignore or working tree.
The shallow pattern scan is not a substitute for GitHub secret scanning/history review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any

from product_analytics.experimentation.cp3_analysis import DESIGN_HASH

REPO_ROOT = Path(__file__).resolve().parents[3]
CASES = {
    'positive': (6000, 1703),
    'null': (6000, 1704),
    'srm': (1200, 1705),
    'underpowered': (60, 1706),
}
SECRET_SIGNS = {
    'openai_key': re.compile(rb'\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{18,}\b'),
    'github_token': re.compile(rb'\b(?:ghp_|gho_|ghu_|ghs_|ghr_)[A-Za-z0-9]{30,}\b'),
    'github_fine_grained': re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{50,}\b'),
    'aws_access_key': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private_key_header': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
}
BLOCKED_NAMES = {'.env', 'id_rsa', 'id_ed25519', '.npmrc', '.pypirc', 'credentials.json', 'service-account.json'}
BLOCKED_SUFFIXES = {'.pem', '.p12', '.pfx', '.key', '.db', '.sqlite', '.sqlite3', '.pyc'}
BLOCKED_DIRS = {'.venv', 'venv', '__pycache__', '.pytest_cache', '.git', '.mypy_cache', '.ruff_cache', 'node_modules'}
DATA_DIRS = {'artifacts', 'outputs', 'logs'}
APPROVED_DATA_PLACEHOLDERS = {'artifacts/.gitkeep', 'outputs/.gitkeep', 'logs/.gitkeep',
                              'data/raw/.gitkeep', 'data/processed/.gitkeep'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suspicious_path(name: str) -> list[str]:
    norm = name.replace('\\', '/')
    if norm.startswith('./'):
        norm = norm[2:]
    parts = PurePosixPath(norm).parts
    if not parts or '..' in parts or name.startswith('/'):
        return ['INVALID_PATH']
    found: list[str] = []
    if any(p in BLOCKED_DIRS for p in parts):
        found.append('CACHE_OR_ENV_DIRECTORY')
    leaf = parts[-1].lower()
    if leaf in BLOCKED_NAMES or (leaf.startswith('.env.') and leaf != '.env.example'):
        found.append('SENSITIVE_FILENAME')
    if PurePosixPath(leaf).suffix in BLOCKED_SUFFIXES:
        found.append('BLOCKED_EXTENSION')
    if norm.startswith('data/raw/') or norm.startswith('data/processed/') or (parts[0] in DATA_DIRS):
        if norm not in APPROVED_DATA_PLACEHOLDERS:
            found.append('GENERATED_OR_PRIVATE_OUTPUT')
    return found


def check_content(name: str, payload: bytes) -> list[str]:
    if name == '.env.example':
        # Placeholder field names should be accepted; actual token values never are.
        pass
    return [f'SECRET_PATTERN_{k}' for k, expression in SECRET_SIGNS.items() if expression.search(payload)]


def audit_tree(root: Path) -> dict[str, Any]:
    """Only inspect distributable project files; report ignored .env presence by path."""
    reasons = []
    inspected = 0
    for file in sorted(root.rglob('*')):
        if not file.is_file() and not file.is_symlink():
            continue
        rel = file.relative_to(root).as_posix()
        parts = PurePosixPath(rel).parts
        # Ignore all known generated outputs/caches, but inspect hidden .env by path.
        if any(x in BLOCKED_DIRS for x in parts) or (parts and parts[0] in DATA_DIRS):
            continue
        if rel.startswith('data/raw/') or rel.startswith('data/processed/'):
            continue
        inspected += 1
        issues = suspicious_path(rel)
        if file.is_symlink():
            issues.append('SYMLINK_PRESENT')
        elif file.stat().st_size <= 3_000_000:
            issues += check_content(rel, file.read_bytes())
        else:
            issues.append('UNEXPECTED_LARGE_SOURCE_FILE')
        reasons.extend({'file': rel, 'code': issue} for issue in issues)
    return {'passed': not reasons, 'inspected_files': inspected, 'findings': reasons}


def audit_index(root: Path) -> dict[str, Any]:
    """Require the real staged Git index and inspect exact blob bytes."""
    def git(*args: str) -> bytes:
        return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout
    try:
        git('rev-parse', '--show-toplevel')
        raw = git('ls-files', '--stage', '-z')
    except (OSError, subprocess.CalledProcessError) as exc:
        return {'passed': False, 'inspected_files': 0,
                'findings': [{'file': '(repository)', 'code': 'GIT_INDEX_UNAVAILABLE'}]}
    findings = []
    files = 0
    for record in filter(None, raw.split(b'\0')):
        left, path = record.split(b'\t', 1)
        mode, oid, stage = left.decode('ascii').split(' ')
        name = path.decode('utf-8', 'replace')
        files += 1
        issues = suspicious_path(name)
        if mode == '120000':
            issues.append('STAGED_SYMLINK')
        try:
            data = git('cat-file', 'blob', oid)
        except (OSError, subprocess.CalledProcessError):
            issues.append('STAGED_BLOB_UNAVAILABLE')
            data = b''
        if len(data) > 3_000_000:
            issues.append('LARGE_STAGED_FILE')
        else:
            issues += check_content(name, data)
        if stage != '0':
            issues.append('UNMERGED_INDEX_ENTRY')
        findings.extend({'file': name, 'code': issue} for issue in issues)
    if files == 0:
        findings.append({'file': '(repository)', 'code': 'EMPTY_GIT_INDEX'})
    return {'passed': not findings, 'inspected_files': files, 'findings': findings}


def audit_evidence(root: Path) -> dict[str, Any]:
    """Check user's FOUR synthetic scenario reports against matching original CSV bytes."""
    cases = []
    issues = []
    for name, (users, seed) in CASES.items():
        d = root / f'cp3_{name}'
        report_file = d / 'cp3_report.json'
        csv_file = d / 'cp3_synthetic_events.csv'
        reasons = []
        try:
            record = json.loads(report_file.read_text(encoding='utf-8'))
            csv_digest = sha(csv_file)
        except (OSError, ValueError) as exc:
            reasons.append('EVIDENCE_MISSING_OR_INVALID')
            record = {}
            csv_digest = None
        if record:
            conditions = {
                'WRONG_CHECKPOINT': record.get('checkpoint') == 'CP3',
                'SCENARIO_MISMATCH': record.get('scenario') == name,
                'USER_COUNT_MISMATCH': record.get('requested_users') == users,
                'SEED_MISMATCH': record.get('seed') == seed,
                'DATA_HASH_MISMATCH': record.get('input_event_csv_sha256') == csv_digest,
                'DESIGN_LOCK_MISMATCH': record.get('preregistration_sha256') == DESIGN_HASH and record.get('design', {}).get('locked_design_sha256') == DESIGN_HASH,
                'DESIGN_CHECK_NOT_RECORDED': record.get('preregistration_checked_before_generation') is True,
                'INVALID_DATA': record.get('data_quality', {}).get('valid') is True and record.get('data_quality', {}).get('unique_users') == users,
                'NON_SYNTHETIC_OR_LIVE_CLAIM': record.get('synthetic_data_only') is True and record.get('live_deployment') is False and record.get('observed_effect_is_real_world_evidence') is False,
                'WRONG_RELEASE_DECISION': record.get('release_decision', {}).get('status') == 'BLOCK_RELEASE',
                'SRM_GATE_INCORRECT': record.get('randomization', {}).get('srm_failed') is (name == 'srm'),
                'WRONG_POWER_GATE': record.get('design', {}).get('achieved_planned_sample') is False,
            }
            reasons.extend(k for k, ok in conditions.items() if not ok)
        cases.append({'scenario': name, 'passed': not reasons, 'issues': reasons,
                      'users': users, 'seed': seed, 'csv_sha256': csv_digest})
        issues.extend(f'{name}:{reason}' for reason in reasons)
    return {'passed': not issues, 'case_count': len(cases), 'cases': cases, 'findings': issues}


def build_audit(*, root: Path, evidence_root: Path | None,
                scan_index: bool) -> dict[str, Any]:
    design_path = root / 'configs/cp3_preregistered_design.json'
    design_hash = sha(design_path) if design_path.is_file() else None
    output: dict[str, Any] = {
        'checkpoint': 'CP4',
        'audit_type': 'offline_synthetic_prepublication',
        'design_lock_valid': design_hash == DESIGN_HASH,
        'design_sha256': design_hash,
        'tree_security': audit_tree(root),
        'evidence': audit_evidence(evidence_root) if evidence_root else None,
        'git_index': audit_index(root) if scan_index else None,
        'caveats': [
            'No real product users, hosted BigQuery, live rollout or independent preregistration.',
            'Pattern scan is limited to known signatures; not full secret scanning or Git history.',
            'Git index scan applies only when requested and does not certify screenshots.',
            'CP4 evidence checks verify structure/hashes/decision invariants, not external outcome truth.',
        ],
    }
    output['passed'] = output['design_lock_valid'] and output['tree_security']['passed'] \
        and (output['evidence'] is None or output['evidence']['passed']) \
        and (output['git_index'] is None or output['git_index']['passed'])
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=REPO_ROOT)
    parser.add_argument('--evidence-root', type=Path, default=None,
                        help='User-generated artifacts root containing cp3_positive/null/srm/underpowered')
    parser.add_argument('--git-index', action='store_true', help='Audit actually staged Git blobs; fails without Git index')
    parser.add_argument('--out', type=Path, default=Path('artifacts/cp4/cp4_audit_report.json'))
    args = parser.parse_args(argv)
    report = build_audit(root=args.project_root.resolve(),
                         evidence_root=args.evidence_root.resolve() if args.evidence_root else None,
                         scan_index=args.git_index)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'checkpoint': 'CP4', 'passed': report['passed'],
                      'design_lock_valid': report['design_lock_valid'],
                      'tree_security': report['tree_security'], 'evidence': report['evidence'],
                      'git_index': report['git_index'], 'report_file': str(args.out)}, indent=2))
    return 0 if report['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
