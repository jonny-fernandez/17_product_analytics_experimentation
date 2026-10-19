# CP2 — Offline product metrics, SQL parity and dashboard

## Scope and what has (and has not) been tested

The CP1 quality gate runs **before** any metric is calculated. The CP2 pipeline implements the original starter checklist items CP4–CP7 and CP14–CP15 **in an offline, synthetic-data form**: event/user/session KPIs, a first-session ordered funnel, D1–D7 UTC acquisition cohorts, descriptive journey and acquisition segments, three attribution baselines, independent SQLite user-grain parity, and a static HTML dashboard. The original CP8–CP13 experimentation/causal items remain CP3; CP16/CP17 release remain CP4. The BigQuery-formatted reference query is **not executed on BigQuery**.

The model uses deterministic made-up users and events and does NOT represent real GA4 or real experimental effects. `baseline` has simulated conversion probabilities A=10%, B=10.5%; realized results are **descriptive** only. An A/B result, p-value, confidence interval or treatment effect must not be reported as decided in CP2.

## Fixed analytic definitions

- **Unit:** `user_id` (one first assignment, one first exposure). `session_id` is used only for session-level metrics.
- **Exposure cohort:** assigned users with a valid first exposure and **complete seven days** of observation. The fixture declares a fixed synthetic observation end of `2026-02-09T00:00:00+00:00`. Users with exposure + 7 days later than this are excluded. This is a generated-fixture completeness contract, **not an observed real-world event collection guarantee**. No missing future events are imputed as purchases.
- **Primary descriptive conversion:** unique eligible exposed users with >=1 ordered purchase in `[first_exposure, first_exposure + 7d)` divided by eligible exposed users. A valid purchase must have a documented order of funnel steps, enforced by CP1 validation. Zero purchasers mean rate 0; zero eligible denominator is a blocked pipeline, not 0%.
- **Revenue per eligible exposed user:** sum of simulated purchase revenue in same window / all eligible users (including zero-revenue users). Currency is synthetic dollars; outlier policy is *not* validated on production data.
- **First-session ordered funnel:** `session_start` (initial eligible entry) -> `view_item` (strictly after exposure in first session) -> `add_to_cart` -> `begin_checkout` -> `purchase`, in ascending time **within the first session**. Step counts are unique users; all must be monotonic. Step-to-step rate is undefined (`N/A`) if previous-step count is zero. This funnel does not track shopping across multiple sessions. It may differ from the **all-session** 7-day purchaser rate.
- **Acquisition cohort:** calendar date in UTC of user's first started session. `D1`–`D7`: user has >=1 new session on the exact UTC date D days after cohort date. Daily cohort denominator includes only complete eligible exposed users and requires a **complete calendar D window**; days without mature follow-up show `N/A`, not zero.
- **Journeys:** number of started sessions from first session through end of seven-day window, at least one. Multichannel user = >=2 distinct channel labels across started sessions. These are simple synthetic channel labels, not real validated UTM attribution.
- **Bounce proxy:** first started session has no `view_item`. This is **NOT** GA4 official engagement/bounce-rate logic.
- **Segmentation:** first-session channel and first-assignment device; descriptive purchaser rate by segment, no significance claims.
- **Attribution:** purchaser credit allocated to (1) first session channel, (2) last session channel, (3) equally across **sessions** in the analysis window. Repeat sessions can give a channel multiple fractional credits. Buyer credits sum to total purchaser users; revenue credits sum to simulated 7-day purchase revenue in each model. No model is causal or estimated incrementality.
- **Data quality / dedup:** reject conflicting/duplicate events with clear diagnostic; **no silent deduplication**. Reject invalid event schema, impossible purchases, missing exposures, assignment disagreements, timezone drift.

## Independent parity boundary

`src/product_analytics/metrics/sql_parity.py` loads validated events to an **in-memory SQLite database** and runs `sql/local_product_metrics.sql` (a separate SQL implementation, not pandas calls). It compares **25 user-grain fields** (user population, variant, device, channel, cohort/first-session and exposure dates, purchase/revenue/error/bounce, session count, ordered funnel, first/last touch and D1–D7 raw indicators). The query covers cohort inputs; the final cohort maturity mask and equal-weight linear multi-touch credit allocation are independently tested using Python invariants but **not SQL-parity certified**. No hosted BigQuery environment is used. SQL equality is an internal implementation cross-check, not independent data validation or external certification.

## Windows PowerShell commands

Download `Project17_CP2_Complete_Replacement.zip` to your `Downloads` folder and run:

```powershell
$base = 'C:\Users\Jonny Fernandez\Documents\github files'
$root = Join-Path $base '17_product_analytics_experimentation'
$zip = Join-Path $env:USERPROFILE 'Downloads\Project17_CP2_Complete_Replacement.zip'
Expand-Archive -LiteralPath $zip -DestinationPath $base -Force
Set-Location -LiteralPath $root
$env:PYTHONPATH = Join-Path $root 'src'
python -m pytest -q
python -m product_analytics.data.cp2_report --scenario baseline --users 500 --seed 42 --out-dir artifacts\cp2_baseline
python -m product_analytics.data.cp2_report --scenario null --users 500 --seed 42 --out-dir artifacts\cp2_null
python -m product_analytics.data.cp2_report --scenario srm --users 500 --seed 42 --out-dir artifacts\cp2_srm
Start-Process (Join-Path $root 'artifacts\cp2_baseline\cp2_dashboard.html')
```

All three runs must show `"sql_parity": {"passed": true, ...}`. The skewed `srm` scenario **passes CP2 event validation**: inferential sample-ratio-mismatch detection will be implemented in CP3. Even if simulated variant B converts more, **do not claim significance in CP2**.

### Negative quality-gate example

```powershell
python -m product_analytics.data.cp2_report --scenario contaminated --users 500 --seed 42 --out-dir artifacts\cp2_invalid
if ($LASTEXITCODE -ne 2) { throw 'Expected contaminated fixture rejection (exit 2)' }
```

This intentionally fails with `CP2 ERROR: Source quality gate rejected contaminated: ...`, and does not produce `cp2_report.json` in the new negative out-dir. Different outputs are generated in separate folders to avoid stale positive reports from prior runs.

### Files to upload to ChatGPT for CP2 Windows verification

- A screenshot showing final `pytest` result and the three positive runs' `sql_parity.passed: true` values.
- `artifacts\cp2_baseline\cp2_report.json`.
- `artifacts\cp2_null\cp2_report.json`.
- `artifacts\cp2_srm\cp2_report.json`.
- A screenshot of `artifacts\cp2_baseline\cp2_dashboard.html` opened locally.

The static dashboard can be opened offline in your browser. No BigQuery, Power BI, network or paid dependency is required.

## Known limitations / to-do

- Synthetic 500-user fixtures are not powered for 5% relative lift; the positive fixture (30% relative lift design) is not used for a causal or significant result.
- The default `2026-02-09` observation end is a fixture-specific promise and should **never** be reused for real logs without external completeness verification.
- No bot-screening model, seasonality adjustment, real lost-event telemetry, multi-country timezone analysis, real session attribution or revenue refunds.
- No real BigQuery job, hosted deployment, A/B effect estimate, multiplicity adjustment, CUPED, SRM hypothesis test or causal effect.
- Original `sql/funnel.sql` has been replaced with an explicit **BigQuery reference query**, but it remains unexecuted and must not be claimed validated in BigQuery.
- For production, use verified ingestion snapshots / documented watermarking; separately verify cohort maturity and follow-up completeness.
