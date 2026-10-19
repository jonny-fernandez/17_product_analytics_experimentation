# Project 17 Checkpoints

- [x] CP1 — Inspect repository, configs, tests, and synthetic-event starter design (read-only audit performed)
- [x] CP2 — Lock event schema, unit of analysis, product context, KPI tree, and data-quality rules
- [x] CP3 — Generate/validate synthetic GA4-style event data
- [x] CP4 — BigQuery/local SQL schema and core event/session metrics
- [x] CP5 — Funnel analysis and conversion diagnostics
- [x] CP6 — Cohort retention and customer-journey analysis
- [x] CP7 — Attribution baselines and limitations
- [x] CP8 — Experiment design: primary metric, guardrails, alpha, power, MDE, sample size
- [x] CP9 — A/B test estimation, confidence intervals, hypothesis testing
- [x] CP10 — Randomization checks and sample-ratio-mismatch detection
- [x] CP11 — Multiple-testing controls and predefined subgroup analysis
- [x] CP12 — CUPED / variance reduction
- [x] CP13 — Causal measurement extension using Project 11 principles where justified
- [x] CP14 — BigQuery/Python cross-validation and reproducibility artifacts
- [x] CP15 — Power BI or equivalent portfolio dashboard/visualizations
- [ ] CP16 — Automated tests, technical/statistical audit, limitations
- [ ] CP17 — Final screenshots and GitHub handoff

**Original CP1–CP15 except optional production-only scope:** verified in offline synthetic scope; CP8–CP13 verified against Windows 88/88 passing tests and all four CP3 evidence scenarios. CP16 is being verified in consolidated CP4; CP17 GitHub/evidence handoff awaits explicit user approval.


## Consolidated portfolio gates (separate from the original numbered list)

- **Consolidated CP1:** starter review and original CP2/CP3 implementation; Windows tests and baseline/contaminated/invalid_event reports verified from screenshots/user uploads October 19, 2026.
- **Consolidated CP2:** original CP4–CP7 and CP14–CP15 completed in offline synthetic form (Python/SQLite/HTML). User baseline/null/SRM report ZIP and dashboard screenshots inspected; hashes/parity/quality all checked. No hosted BigQuery parity was performed.
- **Consolidated CP3:** original CP8–CP13 implemented with an in-package local preregistration lock and new synthetic scenario seeds; Windows pytest 88/88 and four CP3 scenario datasets / reports verified October 19, 2026. No real-world experiment. CUPED on primary and observational extension intentionally excluded for lack of qualifying data; separate CUPED demonstration included.
- **Consolidated CP4:** prepublication security/evidence checks and cross-platform CI workflow implemented, awaiting Python 3.11 Windows evidence and screenshot handoff before GitHub; final commit Windows + Ubuntu CI not yet run.
