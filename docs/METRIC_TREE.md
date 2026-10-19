# CP1 Product Metric Tree — synthetic e-commerce landing-page experiment

**North-star / business outcome:** eligible purchasing users and simulated net purchase value. All metrics below are definitions, **not measured business results**.

| Level | Metric | Exact unit, numerator / denominator or aggregation | Important policy |
|---|---|---|---|
| Primary experiment KPI | 7-day purchaser conversion | users assigned and first exposed with a first qualifying purchase in 7 days / eligible exposed users with complete 7-day follow-up | binary per user, analysis unit user; no post-exposure population cherry-picking |
| Supporting | Revenue per eligible exposed user | sum of eligible 7-day user revenue / eligible exposed users | synthetic dollars; zeros included; pre-specify outlier rules in CP3 |
| Funnel | Step reached | unique eligible users with ordered completion through each step | temporal sequence, consistent initial eligible denominator |
| Funnel | Step-to-step conversion | eligible users completing step k / eligible users completing step k-1 | step k is strictly after prior step; undefined if denominator = 0 |
| Cohort retention | D1–D7 return-session rate | acquisition-cohort users with a new session in specified day window / acquisition-cohort users with complete follow-up | timezone UTC; exclude immature cohorts from that window |
| Journeys | Session count/user | valid started sessions / unique eligible users | preserve multiple sessions per user |
| Acquisition | First/last-touch | first or last observed session channel inside stated window | descriptive only; NOT causal credit |
| Guardrail | Error incidence (lower is better) | eligible exposed users with at least one `error` in 7 days / eligible exposed users with complete window | provisional noninferiority tolerance: +0.5 percentage point |
| Guardrail | First-session bounce rate (lower is better) | eligible exposed users whose first session has no `view_item` / eligible exposed users with a first session | synthetic proxy, NOT official GA4 bounce |
| Diagnostic | Assignment counts | assigned user counts by variant | prespecified expected allocation 1:1; CP3 performs SRM testing |
| Diagnostic | Event quality | invalid event rows and user/session consistency flags | no silently skipped invalid source rows |

For the first-session bounce guardrail, a candidate tolerance is **+1.0 percentage point** absolute. These thresholds require approval/lock before outcome analysis. Guardrails, event loss, SRM and exposure selection can invalidate an apparent benefit even if primary p-value is small.

**Denominator safety:** undefined denominators must remain missing/explicitly undefined, not silently reported as zero. Existing starter `conversion_rate()` and `retention_rate()` are pre-CP2 stubs; do not use them to certify experiment outcomes.
