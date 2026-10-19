-- CP2 SQLite user-grain independent reimplementation.
-- Params: (:observation_end, :observation_end). Timestamp strings normalized to UTC ISO seconds.
-- This query is NOT BigQuery SQL and does not perform inference.
WITH eligible AS (
 SELECT x.user_id, a.variant, a.device,
        s.channel, substr(s.event_timestamp,1,10) AS cohort_day,
        x.event_timestamp AS exposure_ts, s.event_timestamp AS first_start_ts, s.session_id AS first_session,
        strftime('%Y-%m-%dT%H:%M:%S+00:00',x.event_timestamp,'+7 days') AS window_end
 FROM events x
 JOIN events a ON a.user_id=x.user_id AND a.event_name='experiment_assignment'
 JOIN events s ON s.user_id=x.user_id AND s.session_id=x.session_id AND s.event_name='session_start'
 WHERE x.event_name='experiment_exposure'
 AND strftime('%Y-%m-%dT%H:%M:%S+00:00',x.event_timestamp,'+7 days') <= :observation_end
), views AS (
 SELECT e.*, (SELECT min(t.event_timestamp) FROM events t
    WHERE t.user_id=e.user_id AND t.session_id=e.first_session AND t.event_name='view_item'
      AND t.event_timestamp>e.exposure_ts AND t.event_timestamp<e.window_end) AS view_ts
 FROM eligible e
), carts AS (
 SELECT v.*, (SELECT min(t.event_timestamp) FROM events t
    WHERE t.user_id=v.user_id AND t.session_id=v.first_session AND t.event_name='add_to_cart'
      AND t.event_timestamp>v.view_ts AND t.event_timestamp<v.window_end) AS cart_ts
 FROM views v
), checkouts AS (
 SELECT c.*, (SELECT min(t.event_timestamp) FROM events t
    WHERE t.user_id=c.user_id AND t.session_id=c.first_session AND t.event_name='begin_checkout'
      AND t.event_timestamp>c.cart_ts AND t.event_timestamp<c.window_end) AS checkout_ts
 FROM carts c
), funnel AS (
 SELECT c.*, (SELECT min(t.event_timestamp) FROM events t
    WHERE t.user_id=c.user_id AND t.session_id=c.first_session AND t.event_name='purchase'
      AND t.event_timestamp>c.checkout_ts AND t.event_timestamp<c.window_end) AS funnel_purchase_ts
 FROM checkouts c
)
SELECT f.user_id, f.variant, f.device, f.channel, f.cohort_day, f.exposure_ts, f.first_start_ts,
 (SELECT CAST(count(*)>0 AS INTEGER) FROM events t WHERE t.user_id=f.user_id
  AND t.event_name='purchase' AND t.event_timestamp>=f.exposure_ts AND t.event_timestamp<f.window_end) AS purchased_7d,
 (SELECT coalesce(sum(t.revenue),0.0) FROM events t WHERE t.user_id=f.user_id
  AND t.event_name='purchase' AND t.event_timestamp>=f.exposure_ts AND t.event_timestamp<f.window_end) AS revenue_7d,
 (SELECT CAST(count(*)>0 AS INTEGER) FROM events t WHERE t.user_id=f.user_id
  AND t.event_name='error' AND t.event_timestamp>=f.exposure_ts AND t.event_timestamp<f.window_end) AS error_7d,
 (SELECT CAST(count(*)=0 AS INTEGER) FROM events t WHERE t.user_id=f.user_id
  AND t.session_id=f.first_session AND t.event_name='view_item') AS bounce_first_session,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end) AS sessions_7d,
 1 AS funnel_session_start, CAST(f.view_ts IS NOT NULL AS INTEGER) AS funnel_view_item,
 CAST(f.cart_ts IS NOT NULL AS INTEGER) AS funnel_add_to_cart,
 CAST(f.checkout_ts IS NOT NULL AS INTEGER) AS funnel_begin_checkout,
 CAST(f.funnel_purchase_ts IS NOT NULL AS INTEGER) AS funnel_purchase,
 (SELECT t.channel FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end
  ORDER BY t.event_timestamp,t.event_id LIMIT 1) AS first_touch,
 (SELECT t.channel FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end
  ORDER BY t.event_timestamp DESC,t.event_id DESC LIMIT 1) AS last_touch,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND t.channel<>f.channel) AS extra_channel_sessions,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+1 day')) AS d1_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+2 day')) AS d2_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+3 day')) AS d3_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+4 day')) AS d4_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+5 day')) AS d5_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+6 day')) AS d6_return,
 (SELECT count(*) FROM events t WHERE t.user_id=f.user_id AND t.event_name='session_start'
  AND t.event_timestamp>=f.first_start_ts AND t.event_timestamp<f.window_end AND date(t.event_timestamp)=date(f.first_start_ts,'+7 day')) AS d7_return
FROM funnel f ORDER BY f.user_id;
