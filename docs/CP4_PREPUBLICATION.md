# Consolidated CP4 — technical/security prepublication gate

## Verified before implementation

User-supplied CP3 evidence archive `artifacts(1).zip` contained all four CP3 scenario reports and event CSVs. All CSV SHA-256 digests match their report hashes. Scenario ID, seed, sample size, immutable-in-this-build local design hash, SRM condition, data validity, and BLOCK_RELEASE decision matched across all four scenarios. User's Windows screenshot shows **88/88 tests passed under Python 3.10** after installing statsmodels. This is not yet proof of Python 3.11+ compatibility or CI success.

## New CP4 deliverables

- `src/product_analytics/audit/cp4_audit.py`: read-only source-tree audit, exact Git-index blob audit, 4-case user evidence reproducibility audit, design-hash validation and JSON outcome. Returns nonzero on failed checks. No Git changes, cloud traffic or paid API.
- `tests/test_cp4_audit.py`: negative controls including corrupt CSV evidence, wrong design, release bypass, missing report, sensitive/secret-pattern path, ignored `.env`, and verifying staged (not unstaged) Git bytes.
- `requirements-ci.txt`: minimal Python 3.11+ dependencies for full offline project tests without optional BigQuery client.
- `.github/workflows/offline-ci.yml`: Windows and Ubuntu Python 3.11 matrix; full pytest, audit of checkout Git index, and compact synthetic smoke cases. CI must be verified *on the final pushed commit* after publication is explicitly approved.
- `docs/SCREENSHOT_PLAN.md`: screenshot and Word handoff protocol.

## Required Windows CP4 execution (PowerShell)

**Security hard stop:** The original extracted starter contains `.env` from a prior ZIP. Rotate/revoke its API key if real. After preserving any nonsecret placeholders elsewhere, remove the `.env` file from project root before performing CP4 audit or staging files. The CP4 audit intentionally fails if it finds `.env`; `.gitignore` alone is not sufficient. Do not send its contents in chat or screenshots.

Recommended use a clean Python 3.11 environment, not the user's existing Python 3.10 global installation with the `-umpy` metadata warning. Install Python 3.11 locally first if `py -3.11 --version` is unavailable.

```powershell
$base = 'C:\Users\Jonny Fernandez\Documents\github files'
$root = Join-Path $base '17_product_analytics_experimentation'
$zip = Join-Path $env:USERPROFILE 'Downloads\Project17_CP4_Prepublication_Replacement.zip'
Expand-Archive -LiteralPath $zip -DestinationPath $base -Force
Set-Location -LiteralPath $root

# Confirm Python 3.11 is available.
py -3.11 --version
# One-time isolated dependencies. Existing .venv contents never enter Git.
py -3.11 -m venv .venv
$python = Join-Path $root '.venv\Scripts\python.exe'
& $python -m pip install -r requirements-ci.txt
& $python -m pip install -e . --no-deps

# Fails while old .env exists; do not print credential content.
& $python -m pytest -o addopts='' -q
& $python -m product_analytics.audit.cp4_audit --evidence-root artifacts --out artifacts\cp4\cp4_audit_report.json
Get-Content artifacts\cp4\cp4_audit_report.json | ConvertFrom-Json | Select-Object checkpoint, passed, design_lock_valid
```

The Git index audit is intentionally separate because **no new local or GitHub repo has been authorized or created by this package**. Do not run `git init`, `git add`, push or create a public GitHub repository without user approval. When prepublication screenshots have been reviewed and the user authorizes local Git preparation, inspect the actual staged index:

```powershell
& $python -m product_analytics.audit.cp4_audit --evidence-root artifacts --git-index --out artifacts\cp4\cp4_git_index_report.json
```

`--git-index` fails on an uninitialized repository or empty index, by design. It examines the exact blobs listed by `git ls-files --stage`; a clean working tree is not sufficient. **The scanner checks limited filename/known-token patterns and cannot certify repository history or prove that all secrets are absent.** Review diff, history, image privacy and GitHub settings manually before publication.

## Evidence requested before publication

1. Screenshot of Python 3.11 and `pytest` summary.
2. `artifacts/cp4/cp4_audit_report.json` with `passed:true`, four evidence cases passed and no secret file findings.
3. Screenshot of CP2 baseline metrics / parity and HTML dashboard.
4. Screenshot of CP3 positive `BLOCK_RELEASE` even though primary is significant; show reasons.
5. Screenshot of CP3 SRM failure and strict guardrail block.
6. After user approval for **local Git preparation only**, staged-index report and screenshot.
7. Genuine screenshots of all required sections supplied as originals to produce the prepublication Word handoff with embedded PNG, exact filename and description. User confirms saved screenshot folder before any public push.
8. Only after explicit GitHub and MIT authorization: publish, verify actual pushed SHA and both `offline-ubuntu-latest-py311` and `offline-windows-latest-py311` CI jobs. Capture final CI screenshot afterward.
9. Resume update ONLY after actual evidence and publication verification, using the latest master DOCX input and exact `Jonnathan_Fernandez_Offline_Master_Resume.docx` output. No invented business outcomes or production claims.

## Limits

All benchmark and causality demonstrations are offline synthetic. The locally authored synthetic scenarios are not a blind independent holdout. Local preregistration is unsigned. CUPED is a separate synthetic demo and not used for the conversion effect. No real hosted BigQuery validation, Power BI, cloud deployment, customer behavior, paid LLM traffic, or real-world causal effect is claimed.
