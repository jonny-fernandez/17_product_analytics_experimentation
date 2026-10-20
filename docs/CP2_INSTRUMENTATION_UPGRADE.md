# Project 17 — CP2 additive event instrumentation upgrade

**Status:** Local implementation and Linux regression testing; Windows/Ubuntu CI and operator screenshots **not yet verified** for this upgrade.

## Baseline preservation

The authoritative uploaded baseline is commit `21e13ffa44470ac362d1b812c428e034ae1bd3ef` with **110/110 passing Windows tests** (105 seconds) in the user's October 20, 2026 recovered evidence. The files `src/product_analytics/schemas.py`, `src/product_analytics/data/synthetic_events.py`, original metric and SQL implementations, and four locked experiment datasets/designs are **not modified** by this patch. This upgrade adds a separate ingestion adapter and tests. Do not merge sample browser event data into published historical experiment claims.

## Tracking contract and data ownership

- Source of truth: [`configs/tracking_plan_v1.json`](../configs/tracking_plan_v1.json), version `1`. Each event uses an `object_action` name, a specified `client`/`server` source, a canonical legacy `EventRecord` mapping, and an exact property allowlist. There is no blanket property bag. Unknown versions, events, sources, fields, or unauthorized PII-shaped identifiers are quarantined.
- Consent boundary: the browser sends **no tracking requests** unless the user explicitly selects the demo consent checkbox. Server `/api/start` checks consent before generating a random, opaque synthetic actor and session. The browser uses neither cookies nor localStorage; it does not read or send the user's email, IP, browser fingerprint or device ID.
- Source boundary: event **names** are enforced by the server endpoints. `/api/event` accepts only the three client events. `/api/purchase` is a server-confirmed synthetic order (fixed $25) after completing the mock funnel. The server-generated assignment, start, exposure and purchase cannot be supplied through client-event requests.
- Adapter: `src/product_analytics/instrumentation/core.py` converts accepted envelopes into the original strict `EventRecord` type without changing the old schema. SQLite stores canonical content and hashes for accepted events; quarantine stores only error codes and synthetic event IDs, not raw rejected payloads.
- One local synthetic session per user. User IDs, session IDs and event IDs use bounded, opaque `u_`, `s_`, and `evt_` patterns. **This is NOT secure authentication/identity verification; the local browser demo is not a multi-tenant API.**

| Recorded event | Capture source | Canonical legacy event | Payload properties |
| --- | --- | --- | --- |
| `experiment_assigned` | server | `experiment_assignment` | none |
| `session_started` | server | `session_start` | none |
| `experiment_exposed` | server | `experiment_exposure` | none |
| `product_viewed` | client | `view_item` | none |
| `cart_item_added` | client | `add_to_cart` | none |
| `checkout_started` | client | `begin_checkout` | none |
| `order_purchased` | server | `purchase` | `revenue` (bounded positive synthetic amount) |

## Ingestion semantics and monitoring

- Accept only explicit UTC timestamps; reject events over five minutes in the future or more than 48 hours late relative to **ingest clock**. For CI, historical synthetic event times are replayed with matching **simulated** ingest clocks rather than bypassing the rule.
- Duplicate `event_id` with byte-equivalent canonical envelope becomes `duplicate` (no second count). Same ID with different payload is `id_conflict` and quarantined. SQLite uniqueness prevents concurrent double insertions. Arrival-time order can differ from event-time order; the downstream strict validator uses event-time order before metric computation.
- Accepted events are not by themselves certified to be complete user journeys. The **fail-closed quality gate** rejects invalid assignment/exposure/session/funnel chronologies. Any quarantined attempts block governed metric release; they remain in the quality-monitor report.
- Observability: accepted/quarantined counts and reason codes, local one-hour received volume, minimum volume, configurable expected-hourly-volume deviation above 50%, ingestion lag above 300 seconds, and quality-validator codes. These are deterministic thresholds, not learned drift or a production SLA.
- **Seven-day KPI denominator**: before publishing conversion/retention numbers, every ingested synthetic actor must have passed the legacy validator and have a full seven-day observation window after exposure. If any user's window is immature, results are `BLOCK` with `INCOMPLETE_7_DAY_WINDOW`. On eligible data, the original Python user metrics and independent SQLite results must agree across 25 user-grain fields.
- The window check cannot prove that a real upstream event collector delivered *all* actual events. There are no independently verified source-completeness SLAs. This is why it remains a local, synthetic-only demonstration.

## Reproduce on Windows PowerShell (working repo root)

Use the existing Project 17 virtual environment from CP1, or create a fresh one after placing this patch into a **separate working copy**. Do not delete your baseline checkout.

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-ci.txt
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps
& .\.venv\Scripts\python.exe -m pytest -o addopts='' -q
```

For a deterministic history-based replay (use a new, empty output directory each time):

```powershell
& .\.venv\Scripts\python.exe -m product_analytics.instrumentation.demo --db artifacts/cp2_upgrade_demo/events.sqlite --out-dir artifacts/cp2_upgrade_demo --users 24 --seed 1707
```

Expect `"status": "PASS"` and `"sql_parity_passed": true`. Open `artifacts/cp2_upgrade_demo/instrumentation_dashboard.html` and inspect `instrumentation_report.json`, `.sha256`. The replay creates **simulated historic events**, not an observed time series.

For the consent-aware **current-time browser demo**, use a **different** SQLite database and terminal:

```powershell
& .\.venv\Scripts\python.exe -m product_analytics.instrumentation.webapp --port 8765 --db artifacts/cp2_upgrade_web/events.sqlite
```

Visit `http://127.0.0.1:8765` in your browser. Check consent, click **Start simulated session → View product → Add to cart → Start checkout → Confirm simulated order**; click Refresh. Accepted events should be valid; release should be `BLOCK` because the seven-day observation horizon has not matured. This is **expected**, not a bug. Stop the server with Ctrl+C. To rerun on a clean local database, remove only the demo-specific generated `events.sqlite` after stopping the server. Never delete source files or published evidence.

Linux/macOS users substitute `.venv/bin/python` for the Windows venv path.

## Acceptance tests / limitations

- Original baseline: 110 passing tests on user's Windows machine, from the recovered CP1 evidence (immutable pre-upgrade).
- Upgrade adds 25 deterministic unit/negative/integration tests (including a local HTTP listener), as of this patch. Any upgraded full-suite total, OS support or CI green status must be **independently rerun and observed** after applying files.
- No live GA4/Segment/PostHog or production BigQuery ingestion; no deployed service, real customer data, enterprise authentication, browser instrumentation coverage, cloud SLA or measured business lift.
- Only expose this toy HTTP server on `127.0.0.1`. Do not publicly expose it, import personnel records, or use this as a security-certified collector.
- Negative attempts are intentionally logged without payloads; rate limiting, full web authentication, CSRF hardening, monitoring alert delivery, JS UI automated testing, and multi-session visitor identity are outside the local CP2 scope.

## CP3 and CP4 follow-up

CP3: user runs the patched suite on Windows, verifies the local web flow, report hash, tampered-event quarantine, and CI. Record exact command output/screenshots. CP4: prepare the editable Word screenshot handoff with exact filenames and capture commands **before** any GitHub publishing; release/update the README and master resume only with explicit confirmation.
