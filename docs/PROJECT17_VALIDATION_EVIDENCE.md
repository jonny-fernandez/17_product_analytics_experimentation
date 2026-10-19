# Project 17 — Verified offline evidence and publication status

This document distinguishes user-observed local checks from a future GitHub Actions verification.

## Verified on the user's Windows workstation

- Python `3.12.0` isolated virtual environment.
- `107 passed in 111.41 seconds` on the CP4 pytest suite.
- CP4 source-tree and synthetic evidence audit passed: 4/4 scenarios, 0 pattern findings.
- Git staging audit passed before publication assets: **55 staged paths**, no detected findings, zero whitespace errors.
- CP2 baseline from deterministic data: 500 eligible users / 60 purchasers / 12.00% conversion / $6,550 synthetic revenue; SQLite↔Python parity passed.
- CP3 positive/negative scenario reports and event CSV digests matched the local evidence; all four scenarios blocked release by design (positive, null, SRM, underpowered).

## Not claimed

- GitHub Actions passing on final commit: **pending publication and verification**.
- Real production data, real online experiments, independent preregistration, BigQuery execution, deployed Power BI dashboard, live rollout or business impact.
- Complete secret exposure/history certification: not provided by the local pattern scanner.

The code and screenshot bundle may be prepared for public publication under the separately authorized MIT license, but no public repository status or CI result is established by this document itself.
