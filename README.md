# Project 17 — Product Analytics, Experimentation & Causal Measurement Platform

A **fully offline, reproducible portfolio project** for event-level product analytics and disciplined A/B experiment evaluation. It uses **deterministic synthetic user/event data**, Python, local SQLite, and a self-contained HTML dashboard. It does **not** use real customers, hosted GA4, production BigQuery, paid models, or production traffic.

## What the system demonstrates

| Area | Implemented scope |
| --- | --- |
| Event quality | Typed UTC event contracts; eligible exposure and assignment timing; synthetic session/purchase journeys; invalid/duplicate/assignment-conflict negative cases. |
| Product measurement | 7-day purchase conversion, revenue, ordered first-session funnels and drop-off, D1/D3/D7 retention, cohorts, device/channel segments, repeat sessions, and journeys. |
| Attribution | First-touch, last-touch, and linear multi-touch **descriptive** credit comparisons; no causal attribution claims. |
| SQL reconciliation | Independent in-memory SQLite calculations cross-checked against Python at the user/metric level (25-field parity in verified CP2 fixtures). |
| Reporting | Reproducible CSV/JSON artifacts and a self-contained HTML dashboard. |
| Experimentation | Locked local experiment design, randomization/SRM checks, predeclared conversion outcome and guardrails, effect estimates, confidence intervals, power/MDE/sample planning, multiplicity controls, separate synthetic CUPED illustration. |
| Safety and reproducibility | Fail-closed release gate; tampered-evidence and credential-pattern checks; staged-Git-index audit; Python/pytest regression suite; Windows and Ubuntu GitHub Actions workflow. |

### Offline product dashboard

![Synthetic product analytics baseline: KPIs and SQLite parity](docs/screenshots/02_cp4_baseline_kpis_parity.png)

![Ordered first-session conversion funnel](docs/screenshots/03_cp4_ordered_funnel.png)

More **genuine user-captured screenshots**, with exactly named files, are in [docs/screenshots](docs/screenshots/) and [the evidence guide](docs/SCREENSHOT_PLAN.md).

## Verified local evidence (October 2026)

- **107/107 pytest checks passed** on the user's Windows machine with Python **3.12.0**.
- Baseline synthetic example: **500 eligible users**, **60 purchasers**, **12.00% conversion**, **$6,550** synthetic revenue; Python↔SQLite parity passed.
- Four locally generated CP3 scenarios were independently validated for structure, preregistration hash, event-CSV SHA-256, and expected fail-closed decisions.
- The local, staged Git-index audit passed with **55 staged paths and zero recognized findings** **before** the final publication documentation/screenshots were added. Re-run it on the final staged files before pushing.
- CI workflow includes Python **3.11** across GitHub-hosted **Ubuntu and Windows**; a passing local Windows run **does not imply** GitHub Actions has passed. Verify the **actual pushed commit** and both jobs after publication.

### A/B evaluation: a significant result can still be blocked

Synthetic positive scenario (6,000 assigned users, seed 1703): observed conversion difference **+3.45 percentage points** (95% CI approximately **+1.82 to +5.08 pp**, two-sided p approximately **0.000036**). The locked decision is **`BLOCK_RELEASE`**, not an approval: sample size is below the prespecified 5% relative-MDE plan, and strict guardrails have not been cleared. A broken-allocation SRM scenario and an underpowered scenario also correctly block release. This is an illustrative controlled synthetic fixture, **not an observed real-world causal effect**.

![Positive synthetic experiment correctly blocked from release](docs/screenshots/05_cp4_positive_release_block.png)

See [CP3 implementation](docs/CP3_IMPLEMENTATION.md), [experiment design](docs/EXPERIMENT_DESIGN.md), and [locked design](configs/cp3_preregistered_design.json).

## Reproduce locally

**Requirements:** Python 3.11+; no cloud account or API keys. The commands below run with an isolated environment.

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\python.exe
# macOS/Linux:       .venv/bin/python
python -m pip install -r requirements-ci.txt
python -m pip install -e . --no-deps
python -m pytest -o addopts='' -q
```

On Windows, activate the virtual environment first or replace `python` with `& .\.venv\Scripts\python.exe` in each command. On macOS/Linux, use `source .venv/bin/activate`.

Generate the reproducible dashboard and statistical scenarios:

```bash
python -m product_analytics.data.cp2_report --scenario baseline --users 500 --seed 42 --out-dir artifacts/cp2_baseline
python -m product_analytics.data.cp3_report --scenario positive --users 6000 --seed 1703 --out-dir artifacts/cp3_positive
python -m product_analytics.data.cp3_report --scenario null --users 6000 --seed 1704 --out-dir artifacts/cp3_null
python -m product_analytics.data.cp3_report --scenario srm --users 1200 --seed 1705 --out-dir artifacts/cp3_srm
python -m product_analytics.data.cp3_report --scenario underpowered --users 60 --seed 1706 --out-dir artifacts/cp3_underpowered
python -m product_analytics.audit.cp4_audit --evidence-root artifacts --out artifacts/cp4/cp4_audit_report.json
```

Open `artifacts/cp2_baseline/cp2_dashboard.html` locally. Synthetic CSVs and reports are excluded from Git; generate them instead. The optional Git-index audit uses `--git-index` on a **locally initialized and staged** repository, and does not imply a complete secret-scan or Git-history review.

## Project map

- [Project plan](PROJECT_PLAN.md) and [consolidated checkpoints](CHECKPOINTS.md)
- [Event contract](docs/GA4_EVENT_SCHEMA.md) · [KPI metric tree](docs/METRIC_TREE.md)
- [CP1 validation](docs/CP1_IMPLEMENTATION.md) · [CP2 product analytics](docs/CP2_IMPLEMENTATION.md) · [CP3 experimentation](docs/CP3_IMPLEMENTATION.md)
- [CP4 audit design and limitations](docs/CP4_PREPUBLICATION.md) · [Local verification evidence](docs/PROJECT17_VALIDATION_EVIDENCE.md)
- [SQLite queries](sql/local_product_metrics.sql) · [Tests](tests/) · [GitHub Actions workflow](.github/workflows/offline-ci.yml)
- [Screenshot evidence plan and filenames](docs/SCREENSHOT_PLAN.md)

## Limitations and interpretation

1. All event and experiment results are **synthetic and locally authored**, not independent blind holdouts; local design-lock hashing is not independent preregistration.
2. BigQuery-related starter files are **not evidence of hosted BigQuery runs**; SQL parity was checked via local SQLite. No Power BI service/dashboard was deployed.
3. Descriptive marketing attribution does not establish causality. The CUPED comparison is a separate synthetic demonstration, not the estimator for the displayed binary conversion uplift.
4. No real customer data, traffic, production deployment, system availability, live experiment rollout, real-world fairness, or business impact is claimed.
5. The local Git pattern scanner is not a substitute for professional secret scanning, independent attestation, or a full repository history review.

## License

MIT — see [LICENSE](LICENSE).
