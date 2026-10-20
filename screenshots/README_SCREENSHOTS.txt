PROJECT 17 • CP4 FINAL EVIDENCE IMAGE PACKAGE
Prepared: 2026-10-20

8/8 requested evidence image filenames are present. All PNGs were copied byte-for-byte from the available original input files or from the previously prepared CP4 reference pack, without retouching. The original user-provided images remain unchanged.

01  P17_UPG_01_windows_138_tests.png
    USER-PROVIDED WINDOWS SCREENSHOT of CP3 regression pass (138/138) and evidence collector.
02  P17_UPG_02_tracking_plan_v1.png
    SOURCE-BASED RENDERING of real JSON tracking plan; not a desktop capture.
03  P17_UPG_03_consent_denied.png
    USER-PROVIDED BROWSER SCREENSHOT: consent unchecked; "Consent is required. Nothing was recorded." storefront controls disabled.
04  P17_UPG_04_browser_purchase_gate.png
    USER-PROVIDED BROWSER SCREENSHOT: monitor reports accepted_events=23, schema_valid_rows=23, error_count=0, quarantined_attempts=0, unique_users=4, release=BLOCK with reason=INCOMPLETE_7_DAY_WINDOW. This is a browser scenario result, distinct from the seeded 132-event reproducibility runs; visible monitor status does not on its own confirm that a specific order event was persisted.
05  P17_UPG_05_negative_contract_tests.png
    SOURCE/LOG RENDERING of a local Linux focused negative-test run, not a Windows console capture.
06  P17_UPG_06_seeded_dashboard_parity.png
    BROWSER RENDERING of verified local seeded run_a HTML dashboard from CP3 evidence.
07  P17_UPG_07_sha256_replay_integrity.png
    SOURCE-BASED RENDERING of saved-file SHA-256 verification from CP3 evidence ZIP.
08  P17_UPG_08_cp3_quality_summary.png
    SOURCE-BASED RENDERING of actual CP3 summary and source-tree audit.

RELEASE NOTES
- Original source repository has not been modified or published by packaging these images.
- Before uploading images to a public repository, check Windows paths/usernames or other personal details in image 01 and image 08.
- Passing local tests is not evidence that upgraded GitHub Actions CI has run. Hosted CI verification and final git staging/secret scan remain pending.
- The upgrade is a local synthetic demonstration only; no production deployment, real customer tracking, or professional CDP integration is asserted.
- Do not imply that source/log renderings are user-captured application screenshots.
