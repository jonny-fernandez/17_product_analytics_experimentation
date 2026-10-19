"""SQLite in-memory independent check against Python user-grain metrics."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
import pandas as pd

from product_analytics.metrics.product import _iso

SQL_PATH = Path(__file__).resolve().parents[3] / 'sql' / 'local_product_metrics.sql'
_COMPARE = (
    'variant', 'device', 'channel', 'cohort_day', 'exposure_ts', 'first_start_ts',
    'purchased_7d', 'revenue_7d', 'error_7d', 'bounce_first_session', 'sessions_7d',
    'first_touch', 'last_touch', 'funnel_session_start', 'funnel_view_item',
    'funnel_add_to_cart', 'funnel_begin_checkout', 'funnel_purchase',
    *(f'd{d}_return' for d in range(1, 8)),
)


def check_sql_parity(events: pd.DataFrame, python_users: pd.DataFrame, observation_end: datetime) -> dict:
    """Compare all eligible user metrics using an independent SQLite execution path."""
    if not SQL_PATH.is_file():
        raise FileNotFoundError(f'Missing independent SQL: {SQL_PATH}')
    normalized = events.copy()
    normalized['event_timestamp'] = pd.to_datetime(normalized.event_timestamp, utc=True).map(lambda x: _iso(x.to_pydatetime()))
    normalized['conversion'] = normalized['conversion'].astype(int)
    normalized['revenue'] = normalized['revenue'].astype(float)
    with sqlite3.connect(':memory:') as conn:
        normalized.to_sql('events', conn, index=False)
        conn.execute('CREATE INDEX idx_user_name_ts ON events(user_id,event_name,event_timestamp)')
        query = SQL_PATH.read_text(encoding='utf-8')
        sql_users = pd.read_sql_query(query, conn, params={'observation_end': _iso(observation_end)})
    left = python_users.set_index('user_id')
    right = sql_users.set_index('user_id')
    mismatches = []
    if set(left.index) != set(right.index):
        mismatches.append({'field': 'user_id', 'detail': 'eligible-user populations differ',
                           'python_count': len(left), 'sql_count': len(right)})
    for uid in sorted(set(left.index) & set(right.index)):
        for column in _COMPARE:
            a, b = left.at[uid, column], right.at[uid, column]
            equal = abs(float(a)-float(b)) <= 1e-7 if column == 'revenue_7d' else a == b
            if not equal:
                if len(mismatches) < 20:
                    mismatches.append({'user_id': uid, 'field': column,
                                       'python': str(a), 'sql': str(b)})
                else:
                    return {'passed': False, 'python_users': len(left), 'sql_users': len(right),
                            'mismatches': mismatches, 'truncated': True}
    return {'passed': not mismatches, 'python_users': len(left), 'sql_users': len(right),
            'compared_user_fields': len(_COMPARE), 'mismatches': mismatches, 'sqlite_memory_only': True}
