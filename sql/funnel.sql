-- CP2 BigQuery Standard SQL reference only. NEVER EXECUTED ON BIGQUERY.
-- Requires a staging table with synthetic CP1 event schema and TIMESTAMP event_timestamp.
-- Substitute a qualified staging table only after approval; no default project billing is used.
-- Summary respects first exposure + complete seven-day fixed synthetic observation window.
-- Uses unique validated user assignment and exposure; rejects bad events upstream in Python.
DECLARE observation_end TIMESTAMP DEFAULT TIMESTAMP('2026-02-09 00:00:00+00');
WITH exposure AS (
 SELECT user_id, session_id, event_timestamp AS exp_ts
 FROM `PROJECT.DATASET.events` WHERE event_name='experiment_exposure'
), first_session AS (
 SELECT e.user_id, s.session_id, s.event_timestamp AS start_ts
 FROM exposure e
 JOIN `PROJECT.DATASET.events` s USING(user_id,session_id)
 WHERE s.event_name='session_start'
), eligible AS (
 SELECT e.user_id, f.session_id, e.exp_ts, f.start_ts,
        TIMESTAMP_ADD(e.exp_ts, INTERVAL 7 DAY) AS horizon
 FROM exposure e JOIN first_session f USING(user_id)
 WHERE TIMESTAMP_ADD(e.exp_ts,INTERVAL 7 DAY) <= observation_end
), viewed AS (
 SELECT e.*, (SELECT MIN(t.event_timestamp) FROM `PROJECT.DATASET.events` t
 WHERE t.user_id=e.user_id AND t.session_id=e.session_id AND t.event_name='view_item'
 AND t.event_timestamp>e.exp_ts AND t.event_timestamp<e.horizon) AS view_ts
 FROM eligible e
), carted AS (
 SELECT v.*, (SELECT MIN(t.event_timestamp) FROM `PROJECT.DATASET.events` t
 WHERE t.user_id=v.user_id AND t.session_id=v.session_id AND t.event_name='add_to_cart'
 AND t.event_timestamp>v.view_ts AND t.event_timestamp<v.horizon) AS cart_ts FROM viewed v
), checked_out AS (
 SELECT c.*, (SELECT MIN(t.event_timestamp) FROM `PROJECT.DATASET.events` t
 WHERE t.user_id=c.user_id AND t.session_id=c.session_id AND t.event_name='begin_checkout'
 AND t.event_timestamp>c.cart_ts AND t.event_timestamp<c.horizon) AS checkout_ts FROM carted c
), result AS (
 SELECT c.*, (SELECT MIN(t.event_timestamp) FROM `PROJECT.DATASET.events` t
 WHERE t.user_id=c.user_id AND t.session_id=c.session_id AND t.event_name='purchase'
 AND t.event_timestamp>c.checkout_ts AND t.event_timestamp<c.horizon) AS purchase_ts FROM checked_out c
)
SELECT COUNT(*) AS eligible_exposed_users,
 COUNTIF(view_ts IS NOT NULL) AS viewed_users,
 COUNTIF(cart_ts IS NOT NULL) AS cart_users,
 COUNTIF(checkout_ts IS NOT NULL) AS checkout_users,
 COUNTIF(purchase_ts IS NOT NULL) AS first_session_funnel_purchasers,
 SAFE_DIVIDE(COUNTIF(purchase_ts IS NOT NULL),COUNT(*)) AS first_session_funnel_rate
FROM result;
