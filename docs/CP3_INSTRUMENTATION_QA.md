# Project 17 — CP3 event-instrumentation QA

## Proven CP2 operator baseline (October 20, 2026)

The operator's Windows screenshots show **135 passed in 150.75 seconds**, with a seeded **24-user/132-event** synthetic replay, `status=PASS`, and Python/SQLite parity passing. These prove CP2 functional behavior only; they do not verify the published report's stored-file SHA-256 digest.

## Integrity defect and additive correction

In CP2, `instrumentation_report.json` was written with an ending LF while `instrumentation_report.sha256` hashed the in-memory string **without** that LF. A conventional SHA-256 of the actual file therefore did not match. CP3 writes explicitly encoded UTF-8 report **bytes** with a single LF and hashes those exact bytes, independent of Windows/POSIX text-mode newline translation. Previously generated reports remain evidence of CP2 but must not be treated as checksum-verified; rerun the seeded replay to generate corrected evidence. Do not alter legacy experiment fixtures, assignments, metric definitions, or signed reports in place.

## Acceptance tests

* All **110 original** tests and all **25 CP2** tests must still pass, along with **three CP3 digest/reproducibility tests** (expected total: 138).
* Stored JSON SHA-256 must match its `.sha256` file exactly on Windows.
* Tampering with report bytes must invalidate the original digest.
* Two independent clean 24-user, seed-1707 runs must generate identical report JSON bytes, 132 events, `status=PASS`, and SQL/Python parity.
* Source-tree integrity audit must pass. CI is not independently verified until the user explicitly authorizes a future GitHub push and observes Actions runs on both OSs.
* Existing negative contract, consent, replay/idempotency, event-time order, late/future events, quarantine, and incomplete seven-day observation tests remain in the full suite; do not interpret a full-suite pass as production security validation.

## Operator actions (Windows)

In your **CP2 Upgrade Working** checkout, after applying the included CP3 patch:

```powershell
& .\.venv\Scripts\python.exe scripts\project17_cp3_quality_evidence.py
```

Upload the resulting `artifacts/Project17_CP3_Evidence_*_UTC.zip` and a screenshot of the last JSON status. The runner calls the pytest suite, two seeded synthetic replays, independent on-disk SHA-256 validation, and a source-tree audit. It does NOT stage, commit, push, or connect to a public service. If it fails, upload the ZIP anyway: logs are included.

### Optional browser demonstration (separate manual verification)

```powershell
& .\.venv\Scripts\python.exe -m product_analytics.instrumentation.webapp --port 8765 --db artifacts/cp3_browser_session/events.sqlite
```

In a browser open `http://127.0.0.1:8765`. With consent unchecked, no tracking requests should be sent. Then check consent and follow the simulated product -> cart -> checkout -> purchase flow; refresh the monitor. **BLOCK for incomplete seven-day window is expected**, not a failure. Save screenshots of both the initial consent state and final monitor outcome. Stop the server with Ctrl+C. Keep this demo bound to loopback; no live external events or production credentials.

## Release limits

The work uses synthetic locally generated events. The project is not a genuine Segment, PostHog, GA4, BigQuery, production customer-data, or deployed SaaS implementation. `--git-index` was intentionally omitted from this QA runner because staged Git blobs do not yet include the uncommitted upgrade; the full post-stage index audit belongs to CP4 before an authorized release. Source-tree pattern scans do not replace a full history/secrets review.
