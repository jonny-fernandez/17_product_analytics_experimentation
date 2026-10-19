# Project 17 — Screenshot evidence, verified local runs, and final CI screenshot

Images in `docs/screenshots/` are cropped from user-provided screenshots of the genuine local execution and HTML dashboard; **no terminal or GitHub UI screenshot was fabricated**. They support offline **synthetic-data** results only. The corresponding prepublication Word document exists as a separate portfolio handoff and is intentionally not included in the source repository.

| Filename | What it demonstrates |
| --- | --- |
| `01_cp4_windows_py312_tests.png` | Windows Python 3.12 local `pytest` results: 107 passed. |
| `01b_cp4_python312_environment.png` | Local environment selection / dependencies with Python 3.12. |
| `02_cp4_baseline_kpis_parity.png` | Synthetic baseline eligible-user conversion, revenue and Python↔SQLite PASS. |
| `03_cp4_ordered_funnel.png` | Ordered five-stage first-session funnel and conversion/drop-off. |
| `04a_cp4_retention.png` | Synthetic D1/D3/D7 cohort retention. |
| `04b_cp4_descriptive_attribution.png` | First-, last-, and linear-touch *descriptive* allocation. |
| `05_cp4_positive_release_block.png` | Significant synthetic A/B lift and locked `BLOCK_RELEASE` reasons. |
| `06_cp4_srm_underpowered.png` | Failed sample-ratio and insufficient-power negative scenarios. |
| `07_cp4_security_evidence_audit.png` | Four-scenario integrity and local tree-security audit. |
| `07b_cp4_windows_completed.png` | Completion of local Windows CP4 verification. |

The original uploaded image bytes (or their documented direct crops) are preserved; `SCREENSHOT_MANIFEST.json` contains source names and SHA-256 digests. Screenshots may show a local Windows account path. These are **not production** dashboards or real customer records.

## After publication — final CI proof

Only after pushing the final commit, capture `08_cp4_final_github_actions.png` from the **real GitHub Actions run page** showing the exact run ID, final commit SHA, and passing **Ubuntu** and **Windows** jobs. Do not reuse an earlier run or insert a synthetic image. Verify the run's `headSha` equals `git rev-parse HEAD` and both job conclusions equal `success` before treating the project as published-and-verified. Save this screenshot **outside the repository** in the final portfolio evidence handoff, so that capturing proof does not itself create a new commit and invalidate the captured `headSha`. If you later choose to add it to the repository, that addition creates a new final commit and CI must be rerun on that new SHA.
