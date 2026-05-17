"""index.html 生成器 — 多市场统一排名 + 分市场榜

公司映射从 company_registry 统一读取 (Single Source of Truth)。
"""

import json
from pathlib import Path
from datetime import datetime
from tools.fetcher import fetch_all_8
from tools.ranker import compute_greenblatt, compute_crypto_ranking, compute_pos_crypto_ranking, apply_cross_asset_scores
from tools.company_registry import (
    ticker_to_name_zh, ticker_to_info, MARKET_GROUPS, registry,
)

BASE_DIR = Path('/home/severin/Codelib/股市分析')

NAME_MAP: dict[str, str] = ticker_to_name_zh()
TICKER_INFO: dict[str, tuple[str, str]] = ticker_to_info()

def _find_latest_report(name_zh: str) -> str | None:
    report_dir = BASE_DIR / '分析输出' / name_zh
    if not report_dir.is_dir():
        return None
    html_files = sorted(report_dir.glob('*_综合分析报告.html'))
    if not html_files:
        return None
    return str(html_files[-1].relative_to(BASE_DIR))


def has_report_for_ticker(ticker: str) -> bool:
    name = NAME_MAP.get(ticker, ticker)
    report_dir = BASE_DIR / '分析输出' / name
    return report_dir.is_dir() and any(report_dir.glob('*.html'))



RANK_COLORS = {1: 'r1', 2: 'r2', 3: 'r3'}
CHART_COLORS = ['#059669', '#10b981', '#34d399', '#f59e0b', '#f97316',
                '#2563eb', '#8b5cf6', '#ec4899', '#ef4444', '#dc2626',
                '#84cc16', '#06b6d4', '#a855f7', '#eab308', '#14b8a6']

CSS = """<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#0f172a;--blue:#2563eb;--green:#059669;--red:#dc2626;--amber:#d97706;--slate:#64748b;--border:#e2e8f0;--bg:#f8fafc;--white:#fff;--text:#0f172a;--muted:#94a3b8;--r:8px;--sh:0 1px 3px rgba(0,0,0,.06)}
body{font-family:-apple-system,BlinkMacSystemFont,'Inter','PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.6}
.wrap{max-width:1200px;margin:0 auto;padding:40px 24px 80px}
h1{font-size:28px;font-weight:800;color:var(--navy);margin-bottom:4px}
h2{font-size:18px;font-weight:700;color:var(--navy);margin:32px 0 12px;padding-top:24px;border-top:2px solid var(--border)}
.sub{font-size:13px;color:var(--slate);margin-bottom:32px}
.leaderboard{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:40px}
.rank-card{background:var(--white);border:1px solid var(--border);border-radius:var(--r);padding:20px 24px;box-shadow:var(--sh);position:relative;overflow:hidden;transition:transform .15s,box-shadow .15s}
.rank-card:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.08)}
a.rank-link{text-decoration:none;color:inherit;display:block;cursor:pointer}
.rank-card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px}
.rank-card.r1::before{background:linear-gradient(180deg,#fbbf24,#d97706)}
.rank-card.r2::before{background:linear-gradient(180deg,#94a3b8,#64748b)}
.rank-card.r3::before{background:linear-gradient(180deg,#d97706,#92400e)}
.rank-card .rank-top{display:flex;align-items:baseline;gap:10px;margin-bottom:12px}
.rank-card .rank-pos{font-size:36px;font-weight:800;color:var(--navy);line-height:1}
.rank-card .rank-pos sup{font-size:18px;font-weight:600;color:var(--muted)}
.rank-card .ticker-name{font-size:18px;font-weight:700}
.rank-card .ticker-name small{font-size:12px;color:var(--muted);font-weight:400;margin-left:4px}
.rank-card .score-big{font-size:42px;font-weight:800;color:var(--blue);line-height:1}
.rank-card .score-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.rank-card .metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;margin-top:14px;padding-top:14px;border-top:1px solid var(--border)}
.rank-card .metrics .m label{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px}
.rank-card .metrics .m span{font-size:14px;font-weight:700}
.rank-card .metrics .m .pos{font-size:11px;color:var(--slate);margin-left:4px}
.card{background:var(--white);border:1px solid var(--border);border-radius:var(--r);padding:28px;margin-bottom:20px;box-shadow:var(--sh)}
.card-title{font-size:15px;font-weight:700;margin-bottom:18px;color:var(--navy)}
.t-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:6px;margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
thead{background:var(--bg)}
th{padding:10px 14px;text-align:left;font-size:11px;font-weight:600;letter-spacing:.4px;color:var(--slate);border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid #f1f5f9}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafbff}
tr.hi{background:#f0fdf4}
.market-section{margin-top:16px}
.market-section h3{font-size:15px;font-weight:700;color:var(--navy);margin-bottom:8px;display:flex;align-items:center;gap:6px}
.market-section h3 .count{font-size:12px;font-weight:400;color:var(--muted)}
.chart-wrap{position:relative;margin:16px 0}
.chart-wrap canvas{max-height:300px}
.method{border-left:3px solid var(--blue);background:#f8faff;border-radius:0 8px 8px 0;padding:20px 24px;margin-top:24px}
.method h3{font-size:14px;font-weight:700;margin-bottom:12px;color:var(--navy)}
.method .formula{font-family:'SF Mono','Fira Code',monospace;font-size:12px;color:var(--slate);background:#f1f5f9;padding:8px 14px;border-radius:4px;display:inline-block;margin:8px 0}
.method p{font-size:12px;color:var(--slate);line-height:1.8}
footer{text-align:center;padding:16px 0;font-size:11px;color:var(--muted)}
.crypto-card{border-color:var(--amber) !important;background:linear-gradient(135deg,#fff 0%,#fffbeb 100%) !important}
</style>"""


_CRYPTO_TICKERS = {'BTC', 'ETH', 'SOL', 'BNB'}


def _card_html(name: str, ticker: str, exchange: str, rank_pos: int, total: int,
               score_10: float, score_color: str,
               metrics: list[tuple[str, str, str]],
               is_crypto: bool = False) -> str:
    report_dir = BASE_DIR / '分析输出' / name
    html_files = sorted(report_dir.glob('*.html')) if report_dir.is_dir() else []
    if not html_files:
        return ''
    report_rel = str(html_files[-1].relative_to(BASE_DIR))
    rc = RANK_COLORS.get(rank_pos, '')
    extra_class = ' crypto-card' if is_crypto else ''
    lines = [
        f'<a class="rank-link" href="{report_rel}">',
        f'  <div class="rank-card {rc}{extra_class}">',
        f'    <div class="rank-top">',
        f'      <div class="rank-pos">#{rank_pos}<sup>/{total}</sup></div>',
        f'      <div class="ticker-name">{name} <small>{ticker} · {exchange}</small></div>',
        f'    </div>',
        f'    <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">',
        f'      <div class="score-big" style="color:{score_color}">{score_10:.1f}</div>',
        f'    </div>',
        f'    <div style="font-size:11px;color:var(--muted);margin-bottom:6px">统一十分制评分</div>',
        f'    <div class="metrics">',
    ]
    for label, value, pos in metrics:
        lines.append(f'      <div class="m"><label>{label}</label><span>{value}</span><span class="pos">{pos}</span></div>')
    lines.append('    </div>')
    lines.append('  </div></a>')
    return '\n'.join(lines)


def _build_stock_cards(sorted_stocks: list[tuple], total: int) -> list[str]:
    cards = []
    for i, (ticker, comp, rank, s10, rows) in enumerate(sorted_stocks, 1):
        name = NAME_MAP.get(ticker, ticker)
        exchange = TICKER_INFO.get(ticker, ('', ''))[0]
        color = CHART_COLORS[(i - 1) % len(CHART_COLORS)]
        l1, l2, l3, l4 = rows[0], rows[1], rows[2], rows[3]
        is_crypto = ticker in _CRYPTO_TICKERS
        metrics = [
            (l1.metric, l1.value, l1.rank),
            (l2.metric, l2.value, l2.rank),
            (l3.metric if is_crypto else 'F-Score', l3.value, l3.rank),
            (l4.metric, l4.value, l4.rank),
        ]
        card = _card_html(name, ticker, exchange, i, total, s10, color, metrics, is_crypto=is_crypto)
        if card:
            cards.append(card)
    return cards


def _build_detail_rows(sorted_stocks: list[tuple]) -> list[str]:
    rows_out = []
    for i, (ticker, comp, rank, s10, rows) in enumerate(sorted_stocks, 1):
        name = NAME_MAP.get(ticker, ticker)
        cls = ' class="hi"' if i <= 3 else ''
        l1 = f'{rows[0].value} {rows[0].rank}'
        l2 = f'{rows[1].value} {rows[1].rank}'
        l3 = f'{rows[2].value} {rows[2].rank}'
        l4 = f'{rows[3].value} {rows[3].rank}'
        rows_out.append(
            f'        <tr{cls}><td><strong>{name}</strong></td>'
            f'<td>{l1}</td><td>{l2}</td><td>{l3}</td><td>{l4}</td>'
            f'<td>{comp:.2f}</td><td><strong>{s10}</strong></td><td>{rank}</td></tr>'
        )
    return rows_out


def _build_market_section(label: str, tickers: list[str], all_rankings: list[tuple]) -> str:
    """Build per-market mini leaderboard + chart"""
    market_items = [(t, c, r, s, rows) for t, c, r, s, rows in all_rankings if t in tickers]
    if not market_items:
        return ''
    market_items.sort(key=lambda x: (-x[3], x[0]))

    cards_html = []
    chart_labels = []
    chart_data = []
    chart_colors_local = []
    for i, (ticker, comp, rank, s10, rows) in enumerate(market_items, 1):
        name = NAME_MAP.get(ticker, ticker)
        exchange = TICKER_INFO.get(ticker, ('', ''))[0]
        is_crypto = (ticker in _CRYPTO_TICKERS)
        color = CHART_COLORS[(i - 1) % len(CHART_COLORS)]
        if is_crypto:
            l1, l2, l3, l4 = rows[0], rows[1], rows[2], rows[3]
            metrics = [
                (l1.metric, l1.value, l1.rank),
                (l2.metric, l2.value, l2.rank),
                (l3.metric, l3.value, l3.rank),
                (l4.metric, l4.value, l4.rank),
            ]
        else:
            l1, l2, l3, l4 = rows[0], rows[1], rows[2], rows[3]
            metrics = [
                (l1.metric, l1.value, l1.rank),
                (l2.metric, l2.value, l2.rank),
                ('F-Score', l3.value, l3.rank),
                (l4.metric, l4.value, l4.rank),
            ]
        card = _card_html(name, ticker, exchange, i, len(market_items), s10, color, metrics, is_crypto)
        if not card:
            continue
        cards_html.append(card)
        chart_labels.append(name)
        chart_data.append(s10)
        chart_colors_local.append(color)

    chart_id = f'chart_{label.replace(" ", "").replace("🇺🇸","us").replace("🇭🇰","hk").replace("₿","crypto")}'
    chart_js = f"""new Chart(document.getElementById('{chart_id}'),{{
  type:'bar',data:{{labels:{json.dumps(chart_labels, ensure_ascii=False)},datasets:[{{label:'十分制',data:{json.dumps(chart_data)},backgroundColor:{json.dumps(chart_colors_local)},borderRadius:6,borderSkipped:false}}]}},
  options:{{indexAxis:'y',responsive:true,plugins:{{legend:{{display:false}}}},scales:{{x:{{min:0,max:10,ticks:{{stepSize:2}},grid:{{color:'#f1f5f9'}}}},y:{{grid:{{display:false}}}}}}}}
}})"""

    count = len(market_items)
    return f"""
<h2>{label} <span class="count">({count} 家)</span></h2>
<div class="leaderboard">
{chr(10).join(cards_html)}
</div>
<div class="chart-wrap"><canvas id="{chart_id}"></canvas></div>
<script>{chart_js}</script>"""


def generate() -> str:
    prices = fetch_all_8()
    today = datetime.now().strftime('%Y-%m-%d')

    all_ebit_ev = {t: p.ebit_ev_num for t, p in prices.items() if p.ebit_ev_num is not None}
    all_roic = {t: p.roic_num for t, p in prices.items() if p.roic_num is not None}
    all_f_score = {t: p.f_score for t, p in prices.items() if p.f_score > 0}
    all_peg = {t: p.peg_num for t, p in prices.items() if p.peg_num is not None}

    stock_tickers = [t for t in all_ebit_ev if t not in ('BTC', 'ETH')]
    stock_ebit_ev = {t: all_ebit_ev[t] for t in stock_tickers if t in all_ebit_ev}
    stock_roic = {t: all_roic[t] for t in stock_tickers if t in all_roic}
    stock_f = {t: all_f_score[t] for t in stock_tickers if t in all_f_score}
    stock_peg = {t: all_peg[t] for t in stock_tickers if t in all_peg}

    rankings = {}
    for t in stock_ebit_ev:
        if not has_report_for_ticker(t):
            continue
        r = compute_greenblatt(t, stock_ebit_ev[t], stock_roic.get(t),
                               stock_f.get(t), stock_peg.get(t),
                               stock_ebit_ev, stock_roic, stock_f, stock_peg)
        rankings[t] = r

    # ── 加密排名 ──
    btc = prices.get('BTC')
    if btc and btc.mvrv_z_score > 0 and has_report_for_ticker('BTC'):
        rankings['BTC'] = compute_crypto_ranking(
            btc.mvrv_z_score, btc.hash_rate_eh, btc.f_score, btc.days_since_halving,
            {'BTC': btc.mvrv_z_score}, {'BTC': btc.hash_rate_eh},
            {'BTC': btc.f_score}, {'BTC': btc.days_since_halving},
        )

    pos_tickers = [t for t in ('ETH', 'SOL', 'BNB') if prices.get(t) and prices[t].mcap_tvl_ratio > 0]
    all_mcap_tvl = {t: prices[t].mcap_tvl_ratio for t in pos_tickers}
    all_staking = {t: prices[t].staking_ratio for t in pos_tickers}
    all_crypto_f = {t: prices[t].f_score for t in pos_tickers}
    all_inflation = {t: prices[t].supply_inflation for t in pos_tickers}
    if 'ETH' in pos_tickers and has_report_for_ticker('ETH'):
        eth = prices['ETH']
        rankings['ETH'] = compute_pos_crypto_ranking(
            'ETH',
            eth.mcap_tvl_ratio, eth.staking_ratio,
            eth.f_score, eth.supply_inflation,
            all_mcap_tvl, all_staking, all_crypto_f, all_inflation,
        )

    apply_cross_asset_scores(prices, rankings)

    sorted_stocks = sorted(
        [(t, r.composite_score, r.composite_rank, r.score_10, r.rows) for t, r in rankings.items()],
        key=lambda x: (-x[3], x[0])
    )
    stock_total = len(sorted_stocks)

    stock_cards = _build_stock_cards(sorted_stocks, stock_total)
    detail_rows = _build_detail_rows(sorted_stocks)

    chart_labels = json.dumps([NAME_MAP.get(t, t) for t, _, _, _, _ in sorted_stocks], ensure_ascii=False)
    chart_data = json.dumps([s10 for _, _, _, s10, _ in sorted_stocks])
    stock_colors = json.dumps([CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(sorted_stocks))])

    per_market_sections = []
    all_rankings_for_market = sorted_stocks.copy()

    for label, tickers in MARKET_GROUPS.items():
        sec = _build_market_section(label, tickers, all_rankings_for_market)
        if sec:
            per_market_sections.append(sec)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>投资标的综合排名 — Greenblatt 四层加权</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
{CSS}
</head>
<body>
<div class="wrap">

<h1>🏆 投资标的综合排名</h1>
<p class="sub">Greenblatt 四层加权排名体系 v3.1 · Google Finance 多市场数据 · {today}</p>

<div class="leaderboard">
{chr(10).join(stock_cards)}
</div>

<div class="card">
    <div class="card-title">📊 统一总榜明细 · 桶内综合分 + 跨资产十分制</div>
  <p style="font-size:12px;color:var(--slate);margin-bottom:16px">
        桶内综合分 = 各资产在自身体系内的四层加权位置和，仅用于解释同体系内部相对位置（越小越好）<br>
        统一十分制 = 将股票、BTC、PoS 加密各自的四层原始指标映射到统一语义标尺后加权，范围 1-10（越大越好）<br>
        总榜按统一十分制从高到低排序；加密标的进入总榜，不再单独满分处理
  </p>
  <div class="t-wrap">
    <table>
      <thead>
        <tr><th>标的</th><th>L1</th><th>L2</th><th>L3</th><th>L4</th><th>综合分</th><th>十分制</th><th>排名</th></tr>
      </thead>
      <tbody>
{chr(10).join(detail_rows)}
      </tbody>
    </table>
  </div>
</div>

<div class="card">
  <div class="card-title">📈 综合评分分布（十分制）</div>
  <div class="chart-wrap"><canvas id="mainChart"></canvas></div>
</div>

{"".join(per_market_sections)}

<div class="method">
  <h3>⚙️ 方法论说明</h3>
  <p>
    <strong>股票四层：</strong>L1 EBIT/EV 40% · L2 ROIC 25% · L3 F-Score 25% · L4 PEG 10%<br>
    <strong>BTC 加密四层：</strong>L1 MVRV Z-Score · L2 算力 · L3 链上 F-Score · L4 减半周期<br>
    <strong>PoS 加密四层：</strong>L1 MCap/TVL · L2 Staking比率 · L3 Crypto F-Score(0-6) · L4 年通胀率<br>
    <strong>数据来源：</strong>Google Finance (价格/PE/市值) + 专业源补充 (EBIT/ROIC/F-Score/PEG)<br>
    <strong>加密数据：</strong>CoinGecko + DeFiLlama (免费 API)
  </p>
</div>

<footer>InvestSkill v3.1 · 教育性分析，不构成投资建议 · {today}</footer>
</div>

<script>
new Chart(document.getElementById('mainChart'),{{
  type:'bar',
  data:{{labels:{chart_labels},datasets:[{{label:'十分制评分',data:{chart_data},backgroundColor:{stock_colors},borderRadius:6,borderSkipped:false}}]}},
  options:{{indexAxis:'y',responsive:true,plugins:{{legend:{{display:false}}}},scales:{{x:{{min:0,max:10,ticks:{{stepSize:2}},grid:{{color:'#f1f5f9'}}}},y:{{grid:{{display:false}}}}}}}}
}});
</script>
</body>
</html>"""


def regenerate():
    html = generate()
    path = BASE_DIR / 'index.html'
    path.write_text(html, encoding='utf-8')
    print(f'✅ index.html 已生成 ({len(html):,} bytes)')
