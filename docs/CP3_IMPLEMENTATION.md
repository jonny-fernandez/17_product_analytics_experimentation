# Consolidated CP3 — offline experimentation, inference and release gating

**Delivered for Windows verification; no deployment or real data.** Original checkpoints CP8–CP13 are implemented or explicitly scoped out where identification is unjustified.

## PRE-ANALYSIS LOCK (synthetic demonstration)

The fixed design is recorded in `configs/cp3_preregistered_design.json` and verified by the immutable-in-this-build SHA-256 in `src/product_analytics/experimentation/cp3_analysis.py`. The CLI validates this exact lock **before generating or reading experiment outcomes**. This is an unsigned local design lock and NOT an independent/publicly registered, blind experiment; it can be edited by the code author. Old CP2 synthetic scenario outputs were seen earlier. CP3 exercises different, newly generated seeds for the statistical demonstration.

- Unit: synthetic user ID; 50:50 assigned A/B. The estimand is randomized **intention-to-treat** on the entire assigned cohort. The fixture requires each assigned user to have one exposure and complete 7-day follow-up; missing, immature, or selected users block inference. This avoids describing an exposed-only subset as ITT in an actual product experiment.
- Primary: any purchase within the fixed 7-day postexposure window, analyzed on all assigned users. A 2-sided pooled two-proportion z test, or Fisher's exact test for sparse tables, with a Newcombe 95% score CI for absolute B−A difference. One fixed look, no peeking.
- Planning assumptions: control 10%, 5% **relative** MDE (10.0% → 10.5%, absolute +0.5 percentage points), two-sided alpha 0.05, 80% target power. `statsmodels.NormalIndPower` needs **57,756 assigned eligible users per arm**; 500 or 6,000 in the demonstration is underpowered for that small planned MDE. A scenario with 30% relative lift differs from the MDE and does not waive the power gate.
- SRM: exact 2-sided binomial allocation check, p < .001 blocks release. Inspect ITT assignments, not outcome completers.
- Guardrails: binary user-level error incidence (B−A maximum +0.5 pp) and first-session bounce (+1.0 pp). Conservative one-sided upper bounds split familywise alpha=.025 across both checks; no release until both risks are below their predefined tolerances at the chosen confidence levels. These are *strict*, and small samples will often be inconclusive.
- Interactions: device (mobile/desktop/tablet) and acquisition channel (organic/paid_search/email/direct/social), frozen in advance. The 8 group-vs-complement interaction checks use Wald standard errors and Holm correction, exploratory only. Small cells are labelled insufficient, never interpreted as an absence of heterogeneity. Device/channel must match stable assignment metadata to avoid post-treatment stratification.
- CUPED: event data contain **no measured preassignment covariate**, so the conversion result is NOT CUPED-adjusted. A separate, explicitly labeled continuous synthetic DGP demonstrates CUPED adjustment/variance reduction with preassignment covariate; its estimates are not experimental conversion claims.
- Causal extension: synthetic pseudorandom allocation is only a methodological demonstration. No real-user causal effect, independent external holdout, production attribution, observational effect, hosted BigQuery or live product launch is claimed. Observational causal extension is deferred for lack of suitable covariates, assumptions, and data.
- Release policy: SRM, sample-size, primary significance, and *both* guardrails must clear. Passing this screen is *eligibility for manual review* only, never automatic rollout. Negative, null, failed SRM and underpowered cases are valid outcomes. Actual business decisions require review and real experiments.

## Windows PowerShell execution from project directory

```powershell
$base = 'C:\Users\Jonny Fernandez\Documents\github files'
$root = Join-Path $base '17_product_analytics_experimentation'
$zip = Join-Path $env:USERPROFILE 'Downloads\Project17_CP3_Complete_Replacement.zip'
Expand-Archive -LiteralPath $zip -DestinationPath $base -Force
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root 'src'

# Confirm preregistration bytes before any analysis.
Get-FileHash .\configs\cp3_preregistered_design.json -Algorithm SHA256
python -m pytest -o addopts='' -q

# Four new, independent-seed synthetic experiments (one look each).
python -m product_analytics.data.cp3_report --scenario positive --users 6000 --seed 1703 --out-dir artifacts\cp3_positive
python -m product_analytics.data.cp3_report --scenario null --users 6000 --seed 1704 --out-dir artifacts\cp3_null
python -m product_analytics.data.cp3_report --scenario srm --users 1200 --seed 1705 --out-dir artifacts\cp3_srm
python -m product_analytics.data.cp3_report --scenario underpowered --users 60 --seed 1706 --out-dir artifacts\cp3_underpowered
```

## Share for review

1. Screenshot showing full test count and successful CP3 commands.
2. `artifacts/cp3_positive/cp3_report.json`
3. `artifacts/cp3_null/cp3_report.json`
4. `artifacts/cp3_srm/cp3_report.json`
5. `artifacts/cp3_underpowered/cp3_report.json`

Every report should have `preregistration_checked_before_generation=true` and `release_decision.status=BLOCK_RELEASE` **for these particular demonstration seeds and sizes**. The SRM scenario should additionally report `randomization.srm_failed=true`. Positive scenario is expected to have `primary_outcome.significant_at_locked_alpha=true` but `BLOCK_RELEASE` due to sample size and guardrails. Statistical outcomes may vary with other seeds; never change policy to force a favorable result.

## Security and scope

No `.env`, credentials, caches, private data, hosted queries, paid API usage or precomputed outcomes in the replacement ZIP. The old `.env` from the starter is not deleted during extraction: revoke/rotate any genuine exposed secret and remove it yourself before publication. CP4 will independently inspect Git staging, evidence, reproducibility and CI, and prepare screenshot handoff before publication.
