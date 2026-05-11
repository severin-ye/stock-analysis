"""index.html 生成器 — 多市场统一排名 + 分市场榜"""

import json
from pathlib import Path
from datetime import datetime
from tools.fetcher import fetch_all_8
from tools.ranker import compute_greenblatt, compute_crypto_ranking, compute_pos_crypto_ranking, composite_to_score10

BASE_DIR = Path('/home/severin/Codelib/股市分析')

NAME_MAP: dict[str, str] = {
    'NVDA': '英伟达', 'AAPL': '苹果', 'INTC': '英特尔', 'TSLA': '特斯拉',
    'AMD': '超微半导体', 'MU': '美光', '1810.HK': '小米',
    'LLY': '礼来', 'AVGO': '博通',
    '000660.KS': 'SK海力士', '005930.KS': '三星电子',
    '207940.KS': '三星生物制药', '005380.KS': '现代汽车',
    '0700.HK': '腾讯', '9988.HK': '阿里巴巴', '3690.HK': '美团', '1211.HK': '比亚迪',
    'BTC': '比特币', 'ETH': '以太坊', 'SOL': 'Solana', 'BNB': 'BNB',
}

TICKER_INFO: dict[str, tuple[str, str]] = {
    'NVDA': ('NASDAQ', '英伟达'), 'AAPL': ('NASDAQ', '苹果'),
    'INTC': ('NASDAQ', '英特尔'), 'TSLA': ('NASDAQ', '特斯拉'),
    'AMD': ('NASDAQ', '超微半导体'), 'MU': ('NASDAQ', '美光'),
    'LLY': ('NYSE', '礼来'), 'AVGO': ('NASDAQ', '博通'),
    '1810.HK': ('HKEX', '小米'), '0700.HK': ('HKEX', '腾讯'),
    '9988.HK': ('HKEX', '阿里巴巴'), '3690.HK': ('HKEX', '美团'), '1211.HK': ('HKEX', '比亚迪'),
    '000660.KS': ('KRX', 'SK海力士'), '005930.KS': ('KRX', '三星电子'),
    '207940.KS': ('KRX', '三星生物制药'), '005380.KS': ('KRX', '现代汽车'),
    'BTC': ('Crypto', '比特币'), 'ETH': ('Crypto', '以太坊'),
    'SOL': ('Crypto', 'Solana'), 'BNB': ('Crypto', 'BNB'),
}

REPORT_NAMES: dict[str, str] = {
    '英伟达': '分析输出/英伟达/260511_综合分析报告.html',
    '苹果': '分析输出/苹果/260511_综合分析报告.html',
    '特斯拉': '分析输出/特斯拉/260511_综合分析报告.html',
    '英特尔': '分析输出/英特尔/260511_综合分析报告.html',
    '超微半导体': '分析输出/超微半导体/260511_综合分析报告.html',
    '美光': '分析输出/美光/260511_综合分析报告.html',
    '礼来': '分析输出/礼来/260511_综合分析报告.html',
    '博通': '分析输出/博通/260511_综合分析报告.html',
    'SK海力士': '分析输出/SK海力士/260511_综合分析报告.html',
    '三星电子': '分析输出/三星电子/260511_综合分析报告.html',
    '三星生物制药': '分析输出/三星生物制药/260511_综合分析报告.html',
    '现代汽车': '分析输出/现代汽车/260511_综合分析报告.html',
    '小米': '分析输出/小米/260511_综合分析报告.html',
    '腾讯': '分析输出/腾讯/260511_综合分析报告.html',
    '阿里巴巴': '分析输出/阿里巴巴/260511_综合分析报告.html',
    '美团': '分析输出/美团/260511_综合分析报告.html',
    '比亚迪': '分析输出/比亚迪/260511_综合分析报告.html',
    '比特币': '分析输出/比特币/260511_综合分析报告.html',
    '以太坊': '分析输出/以太坊/260511_综合分析报告.html',
    'Solana': '分析输出/Solana/260511_综合分析报告.html',
    'BNB': '分析输出/BNB/260511_综合分析报告.html',
}

MARKET_GROUP: dict[str, list[str]] = {
    '🇺🇸 美股': ['NVDA', 'AAPL', 'INTC', 'TSLA', 'AMD', 'MU'],
    '🇭🇰 港股': ['1810.HK', '0700.HK', '9988.HK', '3690.HK', '1211.HK'],
    '₿ 加密': ['BTC', 'ETH', 'SOL', 'BNB'],
}

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


def _card_html(name: str, ticker: str, exchange: str, rank_pos: int, total: int,
               composite_rank: str, score_10: float, score_color: str,
               metrics: list[tuple[str, str, str]],
               is_crypto: bool = False) -> str:
    rc = RANK_COLORS.get(rank_pos, '')
    extra_class = ' crypto-card' if is_crypto else ''
    rank_display = composite_rank if composite_rank and composite_rank.startswith('#') else f'#{rank_pos}/{total}'
    lines = [
        f'<a class="rank-link" href="{REPORT_NAMES.get(name, "#")}">',
        f'  <div class="rank-card {rc}{extra_class}">',
        f'    <div class="rank-top">',
    ]
    if is_crypto:
        lines.append(f'      <div class="rank-pos" style="font-size:24px">₿</div>')
    else:
        lines.append(f'      <div class="rank-pos">#{rank_pos}<sup>/{total}</sup></div>')
    lines += [
        f'      <div class="ticker-name">{name} <small>{ticker} · {exchange}</small></div>',
        f'    </div>',
        f'    <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">',
        f'      <div class="score-big" style="color:{score_color}">{rank_display}</div>',
        f'    </div>',
        f'    <div style="font-size:11px;color:var(--muted);margin-bottom:6px">综合排名 (越小越好)</div>',
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
        metrics = [
            (l1.metric, l1.value, l1.rank),
            (l2.metric, l2.value, l2.rank),
            ('F-Score', l3.value, l3.rank),
            (l4.metric, l4.value, l4.rank),
        ]
        cards.append(_card_html(name, ticker, exchange, i, total, rank, s10, color, metrics))
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
    market_items.sort(key=lambda x: x[1])

    cards_html = []
    chart_labels = []
    chart_data = []
    chart_colors_local = []
    for i, (ticker, comp, rank, s10, rows) in enumerate(market_items, 1):
        name = NAME_MAP.get(ticker, ticker)
        exchange = TICKER_INFO.get(ticker, ('', ''))[0]
        is_crypto = (ticker in ('BTC', 'ETH', 'SOL', 'BNB'))
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
        cards_html.append(_card_html(name, ticker, exchange, i, len(market_items), rank, s10, color, metrics, is_crypto))
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

    stock_tickers = [t for t in all_ebit_ev if t not in ('BTC', 'ETH', 'SOL', 'BNB')]
    stock_ebit_ev = {t: all_ebit_ev[t] for t in stock_tickers if t in all_ebit_ev}
    stock_roic = {t: all_roic[t] for t in stock_tickers if t in all_roic}
    stock_f = {t: all_f_score[t] for t in stock_tickers if t in all_f_score}
    stock_peg = {t: all_peg[t] for t in stock_tickers if t in all_peg}

    stock_rankings = {}
    for t in stock_ebit_ev:
        r = compute_greenblatt(t, stock_ebit_ev[t], stock_roic.get(t),
                               stock_f.get(t), stock_peg.get(t),
                               stock_ebit_ev, stock_roic, stock_f, stock_peg)
        stock_rankings[t] = r

    sorted_stocks = sorted(
        [(t, r.composite_score, r.composite_rank, r.score_10, r.rows) for t, r in stock_rankings.items()],
        key=lambda x: x[1]
    )
    stock_total = len(sorted_stocks)

    stock_cards = _build_stock_cards(sorted_stocks, stock_total)
    detail_rows = _build_detail_rows(sorted_stocks)

    max_possible = (
        len(all_ebit_ev) * 0.40 + len(all_roic) * 0.25 +
        len(all_f_score) * 0.25 + len(all_peg) * 0.10
    )

    chart_labels = json.dumps([NAME_MAP.get(t, t) for t, _, _, _, _ in sorted_stocks], ensure_ascii=False)
    chart_data = json.dumps([s10 for _, _, _, s10, _ in sorted_stocks])
    stock_colors = json.dumps([CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(sorted_stocks))])

    per_market_sections = []
    all_rankings_for_market = sorted_stocks.copy()

    # ── 加密排名 ──
    btc = prices.get('BTC')
    crypto_cards = []
    if btc and btc.mvrv_z_score > 0:
        pc = compute_crypto_ranking(
            btc.mvrv_z_score, btc.hash_rate_eh, btc.f_score, btc.days_since_halving,
            {'BTC': btc.mvrv_z_score}, {'BTC': btc.hash_rate_eh},
            {'BTC': btc.f_score}, {'BTC': btc.days_since_halving},
        )
        all_rankings_for_market.append(('BTC', pc.composite_score, '', pc.score_10, pc.rows))

        btc_metrics = [
            (pc.rows[0].metric, pc.rows[0].value, pc.rows[0].rank),
            (pc.rows[1].metric, pc.rows[1].value, pc.rows[1].rank),
            (pc.rows[2].metric, pc.rows[2].value, pc.rows[2].rank),
            (pc.rows[3].metric, pc.rows[3].value, pc.rows[3].rank),
        ]
        crypto_cards.append(
            '<a class="rank-link" href="分析输出/比特币/260511_综合分析报告.html">\n'
            '  <div class="rank-card crypto-card">\n'
            '    <div class="rank-top">\n'
            '      <div class="rank-pos" style="font-size:24px">₿</div>\n'
            '      <div class="ticker-name">比特币 <small>BTC · Crypto</small></div>\n'
            '    </div>\n'
            '    <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">\n'
            f'      <div class="score-big" style="color:var(--amber)">#{pc.composite_rank}</div>\n'
            '    </div>\n'
            f'    <div style="font-size:11px;color:var(--muted);margin-bottom:6px">BTC 综合排名</div>\n'
            '    </div>\n'
            '    <div class="metrics">\n'
            + '\n'.join(
                f'      <div class="m"><label>{l}</label><span>{v}</span><span class="pos">{p}</span></div>'
                for l, v, p in btc_metrics
            ) + '\n'
            '    </div>\n'
            '  </div></a>'
        )

    # ETH/SOL/BNB placeholder (no data yet)
    for ticker, coin_name in [('ETH', '以太坊'), ('SOL', 'Solana'), ('BNB', 'BNB')]:
        cp = prices.get(ticker)
        if not cp:
            crypto_cards.append(
                f'<a class="rank-link" href="#">\n'
                f'  <div class="rank-card crypto-card">\n'
                f'    <div class="rank-top">\n'
                f'      <div class="rank-pos" style="font-size:24px">⚡</div>\n'
                f'      <div class="ticker-name">{coin_name} <small>{ticker} · Crypto</small></div>\n'
                f'    </div>\n'
                f'    <div style="display:flex;align-items:baseline;gap:8px">\n'
                f'      <div class="score-big" style="color:var(--muted)">—</div>\n'
                f'      <div class="score-label">待采集</div>\n'
                f'    </div>\n'
                f'    <div class="metrics">\n'
                f'      <div class="m"><label>数据</label><span>待采集</span><span class="pos">—</span></div>\n'
                f'      <div class="m"><label>数据</label><span>待采集</span><span class="pos">—</span></div>\n'
                f'      <div class="m"><label>数据</label><span>待采集</span><span class="pos">—</span></div>\n'
                f'      <div class="m"><label>数据</label><span>待采集</span><span class="pos">—</span></div>\n'
                f'    </div>\n'
                f'  </div></a>'
            )
        else:
            all_rankings_for_market.append((ticker, 0.0, '', 0.0, []))
            crypto_cards.append(
                f'<a class="rank-link" href="#">\n'
                f'  <div class="rank-card crypto-card">\n'
                f'    <div class="rank-top">\n'
                f'      <div class="rank-pos" style="font-size:24px">⚡</div>\n'
                f'      <div class="ticker-name">{coin_name} <small>{ticker} · Crypto</small></div>\n'
                f'    </div>\n'
                f'    <div style="display:flex;align-items:baseline;gap:8px">\n'
                f'      <div class="score-big" style="color:var(--muted)">—</div>\n'
                f'      <div class="score-label">数据不完整</div>\n'
                f'    </div>\n'
                f'  </div></a>'
            )
    for label, tickers in MARKET_GROUP.items():
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
{chr(10).join(crypto_cards)}
</div>

<div class="card">
  <div class="card-title">📊 四层加权排名明细 · 综合分 → 十分制</div>
  <p style="font-size:12px;color:var(--slate);margin-bottom:16px">
    综合分 = L1×40% + L2×25% + L3×25% + L4×10%（排名位置加权和，越小越好）<br>
    十分制 = round(11 - 综合分 × 10 / {max_possible:.2f}, 1)（1-10，越大越好）<br>
    加密标的用专属四层指标，不参与股票排名
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
