"""Self-contained static HTML dashboard. No network, JavaScript, tracking or external assets."""
from __future__ import annotations
from html import escape


def _fmt(value, pct=False):
    if value is None:
        return 'N/A'
    if pct:
        return f'{value*100:.2f}%'
    if isinstance(value, float):
        return f'{value:,.2f}'
    return str(value)


def _table(rows, columns, pct_columns=()):
    titles = ''.join(f'<th>{escape(label)}</th>' for _, label in columns)
    body = ''.join('<tr>' + ''.join(
        f'<td>{escape(_fmt(row.get(key), key in pct_columns))}</td>' for key, _ in columns
    ) + '</tr>' for row in rows)
    return f'<table><thead><tr>{titles}</tr></thead><tbody>{body}</tbody></table>'


def _bar(rows, label_field, value_field, title):
    values = [max(0, float(item[value_field] or 0)) for item in rows]
    maximum = max(values, default=1) or 1
    content = [f'<h3>{escape(title)}</h3><div class="bars">']
    for item, val in zip(rows, values):
        w = 100 * val / maximum
        content.append(f'<div class="barrow"><span>{escape(str(item[label_field]))}</span>'
                       f'<div class="track"><div class="fill" style="width:{w:.2f}%"></div></div>'
                       f'<b>{escape(str(int(val)))}</b></div>')
    return ''.join(content) + '</div>'


def render_dashboard(tables: dict, scenario: str, seed: int, parity: dict) -> str:
    """HTML content strictly uses prevalidated fixture outputs, escaped before interpolation."""
    s = tables['summary']
    funnel = tables['funnel']
    segments = tables['segments']
    attribution = tables['attribution']
    retention = tables['retention']
    recent_retention = [r for r in retention if r['day'] in (1, 3, 7)]
    cards = [
        ('Exposed users', _fmt(s['eligible_exposed_users'])),
        ('7-day purchaser conversion', _fmt(s['purchase_conversion_7d'], True)),
        ('Synthetic 7-day revenue', '$'+_fmt(s['total_revenue_7d'])),
        ('Repeat-session users', _fmt(s['repeat_session_users_7d'])),
        ('First-session bounce proxy', _fmt(s['bounce_first_session'], True)),
        ('Python ↔ SQLite parity', 'PASS' if parity['passed'] else 'FAIL'),
    ]
    metrics = ''.join('<section class="card"><small>' + escape(k) + '</small><strong>' + escape(v) +
                      '</strong></section>' for k,v in cards)
    css = '''body{font:14px system-ui,Arial,sans-serif;margin:0;background:#f4f6fb;color:#16243a}
main{max-width:1180px;margin:auto;padding:24px}h1{margin-bottom:6px}h2{margin-top:28px}
.notice{background:#fff4d6;border:1px solid #ddb761;padding:12px;border-radius:8px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:20px}
.card{background:white;border:1px solid #dbe2ec;padding:14px;border-radius:10px}
.card small{display:block;color:#55657b}.card strong{font-size:22px;display:block;margin-top:8px}
.panel{overflow:auto;background:white;padding:18px;border:1px solid #dbe2ec;border-radius:10px;margin-top:12px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;border-bottom:1px solid #e0e5ef;padding:8px}th{background:#eef2f8}
.barrow{display:flex;align-items:center;gap:12px;margin:10px 0}.barrow span{width:135px}.barrow b{min-width:48px}
.track{height:18px;background:#edf1f8;flex:1;border-radius:5px;overflow:hidden}.fill{height:100%;background:#315b98}
footer{margin-top:30px;color:#55657b;font-size:12px}'''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Project 17 CP2 | Offline Product Analytics</title><style>{css}</style></head>
<body><main><header><h1>Product Analytics — CP2</h1><p>Scenario: {escape(scenario)} · Seed: {seed} · Offline synthetic data</p></header>
<div class="notice"><strong>Descriptive metrics only.</strong> This dashboard is generated from a controlled synthetic fixture.
No real customers, GA4, production performance, causal attribution, A/B effectiveness or inference is claimed.
7-day windows require a declared synthetic observation horizon. SQL uses in-memory SQLite, not hosted BigQuery.</div>
<div class="cards">{metrics}</div>
<section class="panel">{_bar(funnel, 'step', 'users', 'Ordered first-session funnel')}
{_table(funnel,[('step','Step'),('users','Users'),('from_eligible','From eligible'),('from_previous','Step conversion'),('dropoff_from_previous','Drop-off')],('from_eligible','from_previous','dropoff_from_previous'))}</section>
<section class="panel"><h2>Acquisition segments</h2>
{_table([r for r in segments if r['dimension']=='channel'],[('value','Channel'),('users','Users'),('purchasing_users','Purchasers'),('purchase_rate','Conversion'),('revenue','Revenue')],('purchase_rate',))}</section>
<section class="panel"><h2>Device segments</h2>
{_table([r for r in segments if r['dimension']=='device'],[('value','Device'),('users','Users'),('purchasing_users','Purchasers'),('purchase_rate','Conversion')],('purchase_rate',))}</section>
<section class="panel"><h2>Cohort retention (UTC D1 / D3 / D7)</h2>
{_table(recent_retention,[('cohort_day','First session cohort'),('day','Day'),('cohort_users','Cohort users'),('returning_users','Returning'),('retention_rate','Retention')],('retention_rate',))}</section>
<section class="panel"><h2>Attribution model sensitivity (descriptive only)</h2>
{_table(attribution,[('model','Model'),('channel','Channel'),('buyer_credit','Buyer credits'),('revenue_credit','Revenue credits')])}</section>
<section class="panel"><h2>Journeys</h2>
{_table([tables['journeys']], [('users','Users'),('sessions','Sessions'),('avg_sessions_per_user','Sessions per user'),('repeat_session_users','Repeat users'),('multichannel_users','Multi-channel users')])}</section>
<footer>CP2 portfolio exercise. The live experiment and causal decision remain out of scope until CP3.
No external scripts, assets or calls.</footer></main></body></html>'''
