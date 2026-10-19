# CP1 synthetic GA4-style event contract (v1, portfolio only)

This is **not** a real GA4 export. All user IDs, campaigns, devices, sessions and revenues are made up. One `user_id` is the randomization and primary analysis unit; one `session_id` identifies a synthetic browsing session. `event_id` uniquely identifies one event. Every event has one stable experiment assignment per user.

| Field | Type / rule | Purpose |
|---|---|---|
| `event_id` | nonblank unique string | deterministic event deduplication key |
| `user_id` | nonblank string | user-level assignment/analysis key |
| `session_id` | nonblank string except assignment (null) | session-level calculations |
| `event_timestamp` | timezone-aware UTC; offsets other than `+00:00` rejected | deterministic event time |
| `event_name` | one of `experiment_assignment`, `session_start`, `experiment_exposure`, `view_item`, `add_to_cart`, `begin_checkout`, `purchase`, `error` | strict event type |
| `page` | optional string | simulated page |
| `channel` | `organic`, `paid_search`, `email`, `direct`, `social` | descriptive acquisition |
| `campaign` | optional string | simulated marketing attribution |
| `device` | `mobile`, `desktop`, `tablet` | predefined subgroup |
| `experiment_id` | nonblank string (`landing_page_test` in CP1) | stable experiment identifier |
| `variant` | `A` or `B` | user-level assigned variant on every event |
| `conversion` | binary; `1` only on purchase | event-level purchase flag, not user-level outcome |
| `revenue` | finite nonnegative; positive only on purchase | simulated purchase revenue |

## Ordering and validation

Assignment has no session. Every other event must have a session and a matching user assignment. Exactly one assignment and first exposure exist per generated user. The first session starts after assignment; exposure starts after assignment and its session start. Every purchase follows the ordered same-session chain `session_start → view_item → add_to_cart → begin_checkout → purchase`, strictly increasing in timestamp, and follows exposure. Sessions cannot be shared between users. Device, channel, and campaign must be stable within each session, while channels may change on later sessions.

Reject incomplete schema, unexpected columns, non-UTC/naive timestamps, duplicate event IDs, conflicting assignments, invalid events and impossible purchases. All checks are deterministic. Validation is a quality gate, not a statistical SRM check. For CP2 establish a documented event deduplication policy: **reject on conflicts; do not silently discard duplicate rows**. CP1 emits only validated or intentionally invalid synthetic fixtures and no production data.

## Policy boundaries and limitations

- Only synthetic user IDs; no bots or identities are inferred. Synthetic traffic has **zero bots by construction** and there is no production bot-detection claim.
- The sample generates at most two sessions per user; first exposure only; first eligible purchase in the first session. Later sessions are useful for retention and descriptive multi-touch examples, not a claim of a realistic population.
- Conversion-window eligibility and missing/late events need follow-up data completeness rules in CP2/CP3. Do not include users without a complete seven-day outcome window in finalized analyses.
- Event timestamps are UTC in the generated Python data and are formatted with explicit offsets in CSV. Treat malformed/local-time source records as invalid rather than guessing timezone.
- Validation reports expose deterministic synthetic IDs in examples only, never user records from external sources.
