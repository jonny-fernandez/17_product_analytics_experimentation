# CP1 experiment design — DRAFT, not preregistered/locked

Product surface: **synthetic landing-page e-commerce experiment**. Assignment unit: user ID. Eligible population: one stable assignment and qualifying first exposure after assignment. ITT (all assigned) vs exposed-only estimands require explicit selection-bias review before the chosen primary estimand is locked. CP1's proposed exposed-user primary analysis is **conditional on exposure being assignment-invariant**. Do not claim randomized causal identification if variant affects exposure qualification.

- **Primary outcome candidate:** binary indicator of at least one ordered purchase within [first exposure, first exposure + 7 days] per eligible exposed user, with fully observed follow-up window.
- **Hypothesis:** two-sided H0: pB-pA = 0 vs H1: pB-pA != 0; report absolute difference and relative difference with confidence intervals. No result is estimated during CP1.
- **Alpha / power:** two-sided familywise primary alpha 0.05; target 80% power.
- **Traffic ratio:** 50% assignment A, 50% B, stable across user sessions.
- **Illustrative assumed baseline / MDE:** pA = 0.10, relative MDE = 5% → pB = 0.105; absolute MDE = 0.005. These are design assumptions, **not observed results**.
- **Illustrative sample:** normal-approximation two-sided planning roughly 57,756 eligible users/arm for 0.10 vs 0.105 (subject to later exact computation). Sample **is not** achieved by the default 500-user fixture.
- **Guardrails:** error user-incidence (proposed +0.5 pp noninferiority tolerance) and first-session bounce (proposed +1.0 pp); pre-specify one-sided uncertainty and stopping rules in CP3.
- **SRM:** candidate pre-specified p < 0.001 check vs expected 1:1 allocation; failed SRM triggers investigation/no efficacy release, never reinterpret as treatment impact.
- **Multiplicity:** primary confirmatory test only, then Holm procedure over a declared family of secondary/guardrail tests if testing beyond noninferiority; freeze full family before outcome analysis.
- **Subgroups:** device (mobile, desktop, tablet) and acquisition channel (organic, paid_search, email, direct, social), as specified before looking at results; report N/uncertainty; interaction tests rather than post-hoc significance claims.
- **CUPED:** only pre-assignment covariates with valid complete measurement; no covariates generated as post-exposure information can be used as 'preperiod'. If none exists, skip CUPED.
- **Duration:** to be set using justified eligible-user traffic, full seven-day observation and operational calendar. No inventing throughput or choosing a duration from the sample fixture.
- **Exposure/analysis policy:** preregistration must resolve whether exposure qualification is treatment-invariant; default to randomized ITT when uncertain. Enforce complete data, no peeking, no post-treatment subgroup selection, robust provenance.
- **Audit sequence:** CP1 draft → CP2 event/metric parity → CP3 approve/freeze design and dataset split before outcome analysis → estimation/sensitivity → CP4 independent checks.

**Fixture distinction:** `baseline` uses 10% vs 10.5%; `positive` uses 10% vs 13% (**30% relative uplift, not the configured MDE**); `null` uses equal rates; `srm` simulates 80:20 assignments; `underpowered` caps at 60 users; `contaminated` and `invalid_event` deliberately fail event quality gates. No scenario in CP1 constitutes real randomized evidence.
