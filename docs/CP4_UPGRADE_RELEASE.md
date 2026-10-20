# Project 17 — CP4 additive upgrade release checklist (October 20, 2026)

## Status and scope

The original commit `21e13ffa44470ac362d1b812c428e034ae1bd3ef` remains the rollback reference. The additive work was built in a separate working tree. This project remains a **synthetic, offline/local lab**, not a deployed or production product-data collector or a live CDP integration.

**Verified on user's Windows machine:** CP1 original 110/110; CP2 135/135; CP3 138/138 in 156.27 seconds. CP3 evidence ZIP verified both 132-event seeded replays, Python/SQLite parity, byte-identical JSON, saved SHA-256 checks, and a zero-findings source-tree audit. User's browser images show consent refusal recording nothing, and a separate synthetic session quality monitor with 23 accepted events, 0 schema errors, 0 quarantines, and `INCOMPLETE_7_DAY_WINDOW` / `BLOCK`. The browser monitor screenshot alone does not verify an individual order was persisted.

**Not verified yet:** post-stage Git-index audit on the final file set; final screenshot privacy review; GitHub Actions on the new published commit. A green pre-upgrade Actions run does not verify this upgrade.

## Screenshot provenance

The top-level `screenshots/` directory contains 8 named PNGs, `README_SCREENSHOTS.txt`, and `SHA256SUMS.txt`. The README explains: 01, 03, and 04 are provided Windows/browser screenshots; 02, 05, 07, and 08 are evidence-derived renderings, and 06 is a rendered verified HTML dashboard. These are not interchangeable kinds of capture. Do not imply the synthetic browser screenshots represent actual customer traffic.

Review image 01 for a visible local Windows username/path and image 08 for any local paths before choosing to publish. Replace only with appropriately cropped genuine captures if you wish to remove identifying paths; regenerate the hash manifest after any change.

## Before commit

1. Confirm the repo's HEAD still equals the baseline SHA and that only the intended existing working tree is being modified. Do not copy private HR, payroll, applicant, I-9, or other personnel data into this repo.
2. Verify all 8 images against `screenshots/SHA256SUMS.txt` and inspect `screenshots/README_SCREENSHOTS.txt`.
3. Stage **only** `.github/workflows/offline-ci.yml`, `README.md`, `configs/tracking_plan_v1.json`, the three new documentation files including this release note, `screenshots/`, `scripts/project17_cp3_quality_evidence.py`, `src/product_analytics/instrumentation/`, `tests/test_cp2_instrumentation_upgrade.py`, `tests/test_cp3_instrumentation_quality.py`, and `web/`. Do not stage `.venv`, artifacts, SQLite databases, secrets, or temporary ZIP files.
4. Run `git diff --cached --check` and `python -m product_analytics.audit.cp4_audit --git-index`. Inspect the staged file listing and audit JSON. These checks are bounded, pattern-based local checks, **not** a full history or secret audit.
5. Obtain the user's explicit publication approval. Do not stage more files automatically without review, and never automatically commit/push.

## After approved publication

1. Commit and push the approved changes, noting the new SHA.
2. Visit the Actions run for **that exact SHA**, verify both Ubuntu and Windows jobs reach `success`, and preserve a genuine GitHub Actions screenshot outside the repository so the screenshot itself does not create a new commit.
3. If either job fails, fix with complete replacement files, retest and push only after approval. Do not call the upgrade published-and-verified until both jobs pass on the final SHA.
4. Project 07 follows Project 17; the offline master resume is deliberately unchanged pending explicit approval and accurate new evidence.
