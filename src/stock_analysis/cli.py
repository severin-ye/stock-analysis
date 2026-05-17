"""编排器: fetch → rank → LLM(仅文本) → render → validate

工具与 InvestSkill 的联动:
  1. fetcher 按 InvestSkill 指定的数据源 (marketbeat/trefis) 抓取
  2. ranker 实现 InvestSkill 四层加权排名公式 (纯数学)
  3. 真实数据注入 LLM prompt (LLM 只生成叙述文本)
  4. renderer 使用 InvestSkill 的 Jinja2 模板
  5. validator 检查 HTML 完整性
"""

import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from stock_analysis.registry import ticker_to_name_zh
from stock_analysis.data.fetcher import YF_TICKER_MAP, PriceSnapshot, fetch_all_8, fetch_crypto_public, fetch_yfinance
from stock_analysis.data.sources import source_chain_summary
from stock_analysis.ranking.greenblatt import (
    RankingResult,
    apply_cross_asset_scores,
    compute_crypto_ranking,
    compute_greenblatt,
    compute_pos_crypto_ranking,
)
from stock_analysis.reports.schema import (
    AssetCategory,
    ChartDataset,
    ChartDef,
    ChartType,
    KPIItem,
    ModuleStatus,
    RankingRow,
    ScenarioRow,
    StockReport,
    ValuationMethod,
)
from stock_analysis.reports.stages.render import render_to_file
from stock_analysis.reports.stages.scaffold import scaffold

BASE_DIR = Path(os.environ.get('STOCK_ANALYSIS_HOME', str(Path(__file__).resolve().parent.parent.parent)))
LOG_DIR = BASE_DIR / '.sisyphus' / 'pipeline_logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)


def build_logger(company_name: str) -> logging.Logger:
    log_filename = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{company_name}.log"
    logger = logging.getLogger(f'pipeline.{company_name}')
    logger.setLevel(logging.DEBUG)

    # 清理旧 handler，避免多次调用时 handler 累积导致日志重复输出
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    fh = logging.FileHandler(log_filename, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'
    ))
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(ch)

    logger.info(f"日志文件: {log_filename}")
    return logger


def has_report_for_ticker(ticker: str) -> bool:
    company_name = ticker_to_name_zh().get(ticker, ticker)
    report_dir = BASE_DIR / '分析输出' / company_name
    return report_dir.is_dir() and any(report_dir.glob('*.html'))


def snapshot_report_outputs(output_dir: Path) -> dict[str, int]:
    if not output_dir.exists():
        return {}

    snapshot = {}
    for html_path in sorted(output_dir.rglob('*.html')):
        try:
            snapshot[str(html_path.relative_to(output_dir))] = html_path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def watch_report_outputs(
    output_dir: Optional[Path] = None,
    poll_interval: float = 1.0,
    debounce_seconds: float = 0.5,
    max_polls: Optional[int] = None,
    snapshot_fn=snapshot_report_outputs,
    regenerate_fn=None,
    sleep_fn=time.sleep,
    logger: Optional[logging.Logger] = None,
) -> None:
    output_dir = output_dir or (BASE_DIR / '分析输出')
    if regenerate_fn is None:
        from stock_analysis.generator import regenerate as regenerate_fn

    if logger:
        logger.info(f'[watch] 开始监听: {output_dir}')

    previous_snapshot = snapshot_fn(output_dir)
    polls = 0

    while max_polls is None or polls < max_polls:
        sleep_fn(poll_interval)
        current_snapshot = snapshot_fn(output_dir)
        if current_snapshot == previous_snapshot:
            polls += 1
            continue

        settled_snapshot = current_snapshot
        if debounce_seconds > 0:
            sleep_fn(debounce_seconds)
            latest_snapshot = snapshot_fn(output_dir)
            while latest_snapshot != settled_snapshot:
                settled_snapshot = latest_snapshot
                sleep_fn(debounce_seconds)
                latest_snapshot = snapshot_fn(output_dir)

        if logger:
            logger.info('[watch] 检测到分析输出 HTML 变更，重建 index.html')

        try:
            regenerate_fn()
        except Exception as e:
            if logger:
                logger.warning(f'[watch] index.html 重建失败: {e}')
        else:
            previous_snapshot = settled_snapshot
            if logger:
                logger.info('[watch] index.html 重建完成')

        polls += 1

def build_real_data_prompt(company_name: str, ticker: str, prices: dict[str, PriceSnapshot],
                           rankings: dict[str, RankingResult]) -> str:
    """构建完整真实数据注入块"""
    info = prices.get(ticker)
    rank = rankings.get(ticker)
    if not info:
        return ""

    name_map = ticker_to_name_zh()

    lines = [f"""
## ⚠️ 反幻觉规则 — 必须遵守

1. **所有数值必须来自下方真实数据区块。禁止使用训练数据中的任何数字。**
2. **如果下方区块没有某数字，留空或用 "—" 标记，不要编造。**
3. **排名结果已预计算，禁止修改 layer/rank/value/composite_score。**
4. **叙述和分析可以发挥判断力，但引用的数字必须是下方的。**

---
## 真实采集数据 (按市场数据源矩阵交叉验证, {datetime.now().strftime('%Y-%m-%d')})

### 全部支持标的数据

| 标的 | 股价 | 市值 | YTD | PE | FwdPE | PEG | EBIT/EV | ROIC | F-Score | FCF Yield | Rev Growth | Beta |
|------|------|------|-----|----|-------|-----|---------|------|---------|-----------|------------|------|
"""]
    for t_key in sorted(prices.keys(), key=lambda x: (x != ticker, x)):  # current ticker first
        p = prices[t_key]
        nm = name_map.get(t_key, t_key)
        curr = p.currency
        price_s = f"{curr}{p.price:,.2f}" if isinstance(p.price, (int, float)) and p.price > 0 else str(p.price)
        lines.append(
            f"| {nm}({t_key}) | {price_s} | {p.market_cap} | {p.ytd_change_pct} | "
            f"{p.pe_ratio} | {p.forward_pe} | {p.peg_ratio} | {p.ebit_ev} | {p.roic} | "
            f"{p.f_score}/9 | {p.fcf_yield} | {p.revenue_growth} | {p.beta} |"
        )

    # BTC 特殊指标
    btc = prices.get('BTC')
    if btc and btc.mvrv_z_score:
        lines.append(f"""
### BTC 专属指标
- MVRV Z-Score: {btc.mvrv_z_score}
- 算力: {btc.hash_rate_eh} EH/s
- 距上次减半天数: {btc.days_since_halving} 天
""")

    pos_assets = [p for t, p in prices.items() if t in {'ETH', 'SOL', 'BNB'}]
    if pos_assets:
        lines.append("""
### PoS 加密资产专属指标

| 标的 | MCap/TVL | Staking比率 | 年通胀率 | TVL | Fees | Revenue | 数据源链 |
|------|----------|-------------|----------|-----|------|---------|----------|
""")
        for p in pos_assets:
            lines.append(
                f"| {name_map.get(p.ticker, p.ticker)}({p.ticker}) | {p.mcap_tvl_ratio or '—'} | "
                f"{p.staking_ratio or '—'}% | {p.supply_inflation or '—'}% | {p.tvl or '—'} | "
                f"{p.fees_annualized or '—'} | {p.revenue_annualized or '—'} | {source_chain_summary(p.ticker)} |"
            )

    lines.append("""
### 当前标的数据源 fallback 链
""")
    lines.append(f"- {ticker}: {source_chain_summary(ticker) or info.source}\n")

    # 排名结果
    if rank:
        lines.append("""
### 预计算排名结果 (纯数学, 禁止修改)

| Layer | 维度 | 指标 | 数值 | 排名 | 权重 | 判断 |
|-------|------|------|------|------|------|------|
""")
        for r in rank.rows:
            lines.append(f"| {r.layer} | {r.dimension} | {r.metric} | {r.value} | {r.rank} | {r.weight} | {r.verdict} |")
        lines.append(f"""
综合分: {rank.composite_score:.2f} (越小越好)
综合排名: {rank.composite_rank}
统一十分制: {rank.score_10:.1f}/10
计算: {rank.summary}
""")

    # 安全阈值警告
    if info and info.f_score is not None:
        is_crypto = ticker in {'ETH', 'SOL', 'BNB', 'BTC'}
        is_pos = ticker in {'ETH', 'SOL', 'BNB'}
        f_score_label = "Crypto F-Score" if is_pos else ("链上改编 F-Score" if ticker == 'BTC' else "Piotroski F-Score")
        max_score = 6 if is_pos else 9

        if is_pos and info.f_score <= 1:
            lines.append(f"""
## ⛔ 安全阈值警报 (强制性)

当前 {ticker} 的 {f_score_label} 为 {info.f_score}/{max_score}，属于**高危等级**（链上健康度严重不足）。

**强制约束**:
- s8_signal.signal 必须为 BEARISH 或 NEUTRAL（禁止 BULLISH）
- s8_signal.action 必须为 SELL 或 HOLD（禁止 BUY）
- s8_signal.conviction 必须为 WEAK
- verdict.recommendation 必须为 "观望/回避" 或 "谨慎持有"
- verdict.rec_class 必须为 "bear" 或 "neut"
- verdict.f_score_total 写 "{info.f_score}/{max_score}"（字符串类型，如 "0/6"）
- verdict.composite_rank 不要写入（排名与安全底线冲突时，安全优先）
- 根级 f_score_total 字段必须写纯数字 {info.f_score}（字符串类型，如 "{info.f_score}"）
""")
        elif not is_crypto and info.f_score <= 3:
            lines.append(f"""
## ⛔ 安全阈值警报 (强制性)

当前 {ticker} 的 Piotroski F-Score 为 {info.f_score}/9，属于**高危等级**（财务基本面持续恶化）。

**强制约束**:
- s8_signal.signal 必须为 BEARISH 或 NEUTRAL（禁止 BULLISH）
- s8_signal.action 必须为 SELL 或 HOLD（禁止 BUY）
- s8_signal.conviction 必须为 WEAK
- verdict.recommendation 必须为 "观望/回避" 或 "谨慎持有"
- verdict.rec_class 必须为 "bear" 或 "neut"
""")

    # 全部 8 家排名汇总
    if rankings:
        lines.append("""
### 全部支持标的四层排名汇总 (纯数学, 禁止修改)

| 标的 | L1(EBIT/EV) | L2(ROIC) | L3(F-Score) | L4(PEG) | 综合分 | 统一十分制 | 综合排名 |
|------|------------|----------|-------------|---------|--------|------------|----------|
""")
        sorted_ranks = sorted(
            [(t, r.composite_score, r.score_10, r.composite_rank) for t, r in rankings.items()],
            key=lambda x: (-x[2], x[0])
        )
        for t, score, score_10, c_rank in sorted_ranks:
            nm = name_map.get(t, t)
            rows = rankings[t].rows
            l1 = f"{rows[0].value}({rows[0].rank})"
            l2 = f"{rows[1].value}({rows[1].rank})"
            l3 = f"{rows[2].value}({rows[2].rank})"
            l4 = f"{rows[3].value}({rows[3].rank})"
            lines.append(f"| {nm} | {l1} | {l2} | {l3} | {l4} | {score:.2f} | {score_10:.1f}/10 | {c_rank} |")

    # 当前标的详细信息
    lines.append(f"""
---
### {company_name} 详细数据

| 字段 | 值 |
|------|-----|
| 股价 | {info.currency}{info.price} |
| 市值 | {info.market_cap} |
| 企业价值(EV) | {info.enterprise_value} |
| YTD 涨跌 | {info.ytd_change_pct} |
| 52周低-高 | {info.week52_low} - {info.week52_high} |
| PE (TTM) | {info.pe_ratio} |
| Forward PE | {info.forward_pe} |
| PEG | {info.peg_ratio} |
| EBIT/EV | {info.ebit_ev} |
| ROIC | {info.roic} |
| F-Score 总分 | {info.f_score}/9 |
| FCF Yield | {info.fcf_yield} |
| 营收增速 | {info.revenue_growth} |
| 年营收 | {info.revenue} |
| EBIT | {info.ebit} |
| 净利润 | {info.net_income} |
| Beta | {info.beta} |
| 目标价 | {info.price_target} |
| 数据来源 | {info.source} |
""")

    return "".join(lines)


def yfinance_symbol_for_ticker(ticker: str) -> str:
    for yf_symbol, internal_ticker in YF_TICKER_MAP.items():
        if internal_ticker == ticker:
            return yf_symbol
    return ticker


CRYPTO_INTERNAL_TICKERS = {'BTC', 'ETH', 'SOL', 'BNB'}


def fetch_price_history_points(ticker: str, current_price: float, logger: logging.Logger) -> tuple[list[str], list[float]]:
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("  yfinance 未安装，无法获取过去一年真实走势")
        return [], []

    yf_symbol = yfinance_symbol_for_ticker(ticker)
    hist = yf.Ticker(yf_symbol).history(period='1y', interval='1mo', auto_adjust=True)
    if hist.empty or 'Close' not in hist:
        logger.warning(f"  {ticker}: yfinance 历史价格为空，跳过真实走势覆盖")
        return [], []

    closes = hist['Close'].dropna()
    if closes.empty:
        logger.warning(f"  {ticker}: yfinance Close 序列为空，跳过真实走势覆盖")
        return [], []

    # 价格合理性校验: yfinance 返回的最近月价格必须与实际价格在同一量级
    last_yf_price = float(closes.iloc[-1])
    if current_price > 0 and last_yf_price > 0:
        ratio = max(current_price, last_yf_price) / min(current_price, last_yf_price)
        if ratio > 3:
            logger.error(
                f"  {ticker}: yfinance 价格校验失败！"
                f" yfinance({yf_symbol}) 最近月=${last_yf_price:.2f}, "
                f"真实当前价=${current_price:.2f}, 偏差{ratio:.1f}x > 3x 上限。"
                f" 可能原因: Yahoo Finance 上 {yf_symbol} 不是预期的资产 "
                f"(如 ETH 映射到 Ethan Allen Interiors 而非 Ethereum)。"
                f" 跳过 yfinance 走势数据，使用 LLM 生成的概略图。"
            )
            return [], []

    labels = [idx.strftime('%y.%m') for idx in closes.index]
    data = [round(float(v), 2) for v in closes.values]
    current_label = datetime.now().strftime('%y.%m')
    if labels[-1] != current_label or abs(data[-1] - current_price) / current_price > 0.01:
        labels.append(current_label)
        data.append(round(float(current_price), 2))

    logger.info(f"  {ticker}: 过去一年走势来自 yfinance {yf_symbol}，{len(data)} 个节点")
    return labels, data


def apply_real_price_history(report: StockReport, price_info: PriceSnapshot | None,
                             logger: logging.Logger) -> StockReport:
    if not price_info or not price_info.price:
        logger.warning("  缺少当前价格，无法覆盖过去一年走势")
        return report

    labels, data = fetch_price_history_points(report.ticker, price_info.price, logger)
    if not labels or not data:
        return report

    start = data[0]
    end = data[-1]
    high = max(data)
    low = min(data)
    change_pct = (end / start - 1) * 100 if start else 0.0
    report.s3_body_html = (
        f"<p>过去一年走势采用 Yahoo Finance/yfinance 月度复权收盘价，并以当前缓存价格校准最后一个节点。"
        f"{report.ticker} 从 ${start:.2f} 到 ${end:.2f}，期间高点 ${high:.2f}、低点 ${low:.2f}，"
        f"区间涨跌 {change_pct:+.1f}%。该图表每个节点由程序注入，非 LLM 生成。</p>"
    )

    price_chart = ChartDef(
        chart_id='priceChart', chart_type=ChartType.LINE, section_id='s3',
        labels=labels,
        datasets=[ChartDataset(label=report.ticker, data=data, color='#2563eb', fill=True, tension=0.3)],
        y_axis_label='$', y_axis_format='$', tooltip_prefix='$', tooltip_suffix='',
    )

    for idx, chart in enumerate(report.charts):
        if chart.chart_id == 'priceChart':
            report.charts[idx] = price_chart
            break
    else:
        report.charts.insert(0, price_chart)
    return report


def parse_number(value: str | float | int | None) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    match = re.search(r'-?[\d,.]+', str(value))
    if not match:
        return None
    return float(match.group(0).replace(',', ''))


def parse_rank(rank: str) -> tuple[int, int] | None:
    match = re.search(r'#(\d+)/(\d+)', rank or '')
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def replace_chart(report: StockReport, chart: ChartDef) -> None:
    for idx, existing in enumerate(report.charts):
        if existing.chart_id == chart.chart_id:
            report.charts[idx] = chart
            return
    report.charts.append(chart)


def apply_authoritative_report_data(report: StockReport, price_info: PriceSnapshot | None,
                                    rank: RankingResult | None,
                                    prices: dict[str, PriceSnapshot],
                                    logger: logging.Logger) -> StockReport:
    if not price_info:
        logger.warning("  缺少缓存数据，无法覆盖权威数值")
        return report

    currency = price_info.currency or '$'
    report.cover_price = f"{currency}{price_info.price:,.2f}" if price_info.price else "—"
    report.cover_market_cap = price_info.market_cap or "—"

    is_crypto = report.ticker in {'ETH', 'SOL', 'BNB', 'BTC'}
    is_pos = report.ticker in {'ETH', 'SOL', 'BNB'}

    if is_pos:
        report.cover_kpi = [
            KPIItem(label='当前价格', value=report.cover_price, css_class='up' if price_info.price else 'neut'),
            KPIItem(label='MCap/TVL', value=f"{price_info.mcap_tvl_ratio:.2f}" if price_info.mcap_tvl_ratio else '—', css_class='up' if price_info.mcap_tvl_ratio and price_info.mcap_tvl_ratio < 8 else 'dn'),
            KPIItem(label='TVL', value=price_info.tvl or '—', sub='DeFiLlama'),
            KPIItem(label='Staking率', value=f"{price_info.staking_ratio}%" if price_info.staking_ratio else '—'),
            KPIItem(label='年通胀率', value=f"{price_info.supply_inflation}%" if price_info.supply_inflation else '—'),
            KPIItem(label='Crypto F-Score', value=f"{price_info.f_score}/6"),
        ]
    else:
        report.cover_kpi = [
            KPIItem(label='当前股价', value=report.cover_price, css_class='up' if price_info.price else 'neut'),
            KPIItem(label='YTD', value=price_info.ytd_change_pct or '—', css_class='up' if not str(price_info.ytd_change_pct).startswith('-') else 'dn'),
            KPIItem(label='52周范围', value=f"{price_info.week52_low} - {price_info.week52_high}", sub='来自缓存'),
            KPIItem(label='Forward P/E', value=price_info.forward_pe or '—'),
            KPIItem(label='EBIT/EV', value=price_info.ebit_ev or '—'),
            KPIItem(label='ROIC', value=price_info.roic or '—'),
        ]

    if rank:
        report.greenblatt_ranking = [
            RankingRow(layer=r.layer, dimension=r.dimension, metric=r.metric, value=r.value,
                       rank=r.rank, weight=r.weight, verdict=r.verdict)
            for r in rank.rows
        ]
        report.ranking_summary = rank.summary
        report.composite_score = rank.composite_score
        report.composite_rank_8 = rank.composite_rank
        report.layer_weights = {'L1': '40%', 'L2': '25%', 'L3': '25%', 'L4': '10%'}

        radar_labels = [r.metric for r in rank.rows]
        radar_data = []
        for r in rank.rows:
            parsed = parse_rank(r.rank)
            radar_data.append(round((parsed[1] - parsed[0] + 1) / parsed[1] * 100, 1) if parsed else 0.0)
        replace_chart(report, ChartDef(
            chart_id='valuationRadar', chart_type=ChartType.RADAR, section_id='s5',
            labels=radar_labels,
            datasets=[ChartDataset(label='排名映射分', data=radar_data, color='#2563eb')],
            y_axis_label='', y_axis_format='', tooltip_prefix='', tooltip_suffix='',
        ))

    report.f_score_total = str(int(price_info.f_score or 0))

    # 加密资产使用 Crypto F-Score (0-6)，显示标注
    if is_pos:
        report.s5_body_html = (
            f"<p>估值区块展示缓存事实指标：Forward P/E —、"
            f"PEG —、MCap/TVL {price_info.mcap_tvl_ratio}、Staking {price_info.staking_ratio}%。"
            f"下方「Crypto F-Score」为基于公开链上指标的计算结果；如有「真实数据参考」则来自外部数据源。</p>"
        )
    else:
        report.s5_body_html = (
            f"<p>估值区块展示缓存事实指标：Forward P/E {price_info.forward_pe or '—'}、"
            f"PEG {price_info.peg_ratio or '—'}、EBIT/EV {price_info.ebit_ev or '—'}、ROIC {price_info.roic or '—'}。"
            f"下方「模型分析」框为 LLM 生成的 DCF 情景假设；如有「真实数据参考」则来自外部数据源。</p>"
        )

    # F-Score 安全阈值: 强制覆盖推荐
    if is_pos and price_info.f_score <= 1:
        if report.s8_signal:
            report.s8_signal.action = 'HOLD'
            if report.s8_signal.signal == 'BULLISH':
                report.s8_signal.signal = 'NEUTRAL'
            report.s8_signal.conviction = 'WEAK'
        if report.verdict:
            report.verdict.recommendation = '谨慎持有（Crypto F-Score 0-1/6，链上健康度不足）'
            report.verdict.rec_class = 'neut'
    elif not is_crypto and price_info.f_score <= 3:
        if report.s8_signal:
            report.s8_signal.action = 'HOLD'
            if report.s8_signal.signal == 'BULLISH':
                report.s8_signal.signal = 'NEUTRAL'
            report.s8_signal.conviction = 'WEAK'
        if report.verdict:
            report.verdict.recommendation = '谨慎持有（F-Score ≤ 3/9，财务有风险）'
            report.verdict.rec_class = 'neut'

    report.s6_body_html = (
        "<p>未来展望包含 LLM 生成的悲观/基准/乐观三档情景假设（模型分析）；"
        "如有分析师目标价等真实数据，将在下方「真实数据参考」中单独列出。</p>"
    )

    # 保留 LLM 生成的估值方法，追加真实数据
    if not any(m.name == '当前价格' for m in report.s5_valuation_methods):
        report.s5_valuation_methods.insert(0, ValuationMethod(name='当前价格', value=report.cover_price, probability='事实'))
    if not any(m.name == '分析师目标价' for m in report.s5_valuation_methods):
        report.s5_valuation_methods.insert(1, ValuationMethod(name='分析师目标价', value=price_info.price_target or '—', probability='外部来源'))

    target = parse_number(price_info.price_target)
    current = parse_number(report.cover_price)
    if target and current and current > 0:
        ret = (target / current - 1) * 100
        # 不覆盖 LLM 生成的三档情景，追加分析师目标价作为独立行
        analyst_scenario = ScenarioRow(
            scenario='分析师目标价（真实数据）', probability='—', price_target=f"{currency}{target:,.2f}",
            return_pct=f"{ret:+.1f}%", description='来自缓存目标价，非 LLM 情景估算'
        )
        if report.s6_scenarios:
            report.s6_scenarios.append(analyst_scenario)
        else:
            report.s6_scenarios = [analyst_scenario]

        # S5 dcfChart：当前价 + LLM 三档（如有）+ 分析师目标价
        dcf_labels = ['当前价']
        dcf_data = [round(current, 2)]
        dcf_colors = ['#d97706']
        for s in report.s5_valuation_methods:
            if s.name in ('悲观', 'DCF保守') and parse_number(s.value):
                dcf_labels.append('悲观')
                dcf_data.append(round(parse_number(s.value), 2))
                dcf_colors.append('#dc2626')
            elif s.name in ('基准', 'DCF基准') and parse_number(s.value):
                dcf_labels.append('基准')
                dcf_data.append(round(parse_number(s.value), 2))
                dcf_colors.append('#d97706')
            elif s.name in ('乐观', 'DCF乐观') and parse_number(s.value):
                dcf_labels.append('乐观')
                dcf_data.append(round(parse_number(s.value), 2))
                dcf_colors.append('#059669')
        dcf_labels.append('分析师目标价')
        dcf_data.append(round(target, 2))
        dcf_colors.append('#2563eb')
        replace_chart(report, ChartDef(
            chart_id='dcfChart', chart_type=ChartType.BAR, section_id='s5',
            labels=dcf_labels,
            datasets=[ChartDataset(label='价格', data=dcf_data,
                                   color='#2563eb', point_background_colors=dcf_colors)],
            y_axis_label='$', y_axis_format='$', tooltip_prefix='$', tooltip_suffix='',
        ))

        # S6 scenarioChart：LLM 三档（如有）+ 分析师目标价
        sc_labels = []
        sc_data = []
        sc_colors = []
        for s in report.s6_scenarios:
            if s.scenario in ('悲观', '悲观情景') and parse_number(s.return_pct) is not None:
                sc_labels.append('悲观')
                sc_data.append(round(parse_number(s.return_pct), 1))
                sc_colors.append('#dc2626')
            elif s.scenario in ('基准', '基准情景') and parse_number(s.return_pct) is not None:
                sc_labels.append('基准')
                sc_data.append(round(parse_number(s.return_pct), 1))
                sc_colors.append('#d97706')
            elif s.scenario in ('乐观', '乐观情景') and parse_number(s.return_pct) is not None:
                sc_labels.append('乐观')
                sc_data.append(round(parse_number(s.return_pct), 1))
                sc_colors.append('#059669')
        # 分析师目标价回报
        sc_labels.append('分析师目标价')
        sc_data.append(round(ret, 1))
        sc_colors.append('#2563eb')
        replace_chart(report, ChartDef(
            chart_id='scenarioChart', chart_type=ChartType.BAR, section_id='s6',
            labels=sc_labels,
            datasets=[ChartDataset(label='预期回报%', data=sc_data, color='#2563eb',
                                   point_background_colors=sc_colors)],
            y_axis_label='%', y_axis_format='%', tooltip_prefix='', tooltip_suffix='%',
        ))

    peer_labels = []
    peer_data = []
    for t, p in prices.items():
        val = parse_number(p.forward_pe)
        if val is not None and val > 0:
            peer_labels.append(ticker_to_name_zh().get(t, t))
            peer_data.append(round(val, 2))
    if peer_labels and peer_data:
        replace_chart(report, ChartDef(
            chart_id='peerCompareChart', chart_type=ChartType.BAR, section_id='s5',
            labels=peer_labels,
            datasets=[ChartDataset(label='Forward P/E', data=peer_data, color='#2563eb')],
            y_axis_label='x', y_axis_format='', tooltip_prefix='', tooltip_suffix='x',
        ))

    logger.info("  已用 prices.json/ranker/yfinance 覆盖关键数值与图表")
    return report


OUTPUT_SCHEMA = """
返回 JSON 结构 (字段名必须精确匹配, 但数值从上方真实数据区块取):

{
  "ticker": "NVDA", "company_name": "英伟达", "company_name_en": "NVIDIA",
  "exchange": "NASDAQ", "sector": "半导体", "asset_category": "stock",
  "report_date": "2026-05-11", "data_date": "2026-05-10 收盘",
  "cover_title": "NVDA — 英伟达 综合投资分析",
  "cover_price": "从上表取", "cover_market_cap": "从上表取",

  "cover_kpi": [
    {"label": "当前股价", "value": "从上表取", "css_class": "up/dn"},
    {"label": "YTD", "value": "从上表取", "css_class": "up/dn"},
    {"label": "52周范围", "value": "从上表取", "sub": "高位/低位/中位"},
    {"label": "Forward P/E", "value": "从上表取"},
    {"label": "EBIT/EV", "value": "从上表取"},
    {"label": "ROIC", "value": "从上表取"}
  ],

  "s1_price_changes": [
    {"dimension": "YTD", "change_pct": "从上表取", "corresponding_price": "", "probability_weight": "—", "industry_compare": "SOX对比"},
    {"dimension": "52周极端", "change_pct": "", "corresponding_price": "", "probability_weight": "—", "industry_compare": ""}
  ],
  "s1_core_judgment": "基于排名结果的一句话总结",

  "s2": {"title": "🏢 公司概览", "subtitle": "", "body_html": "<p>商业模式描述</p>",
         "key_metrics": [{"label": "市值", "value": "从上表取", "note": ""}]},

  "s3_body_html": "<p>过去一年走势分析</p>",

  "s4": {"title": "⚔️ 竞争格局", "subtitle": "", "body_html": "<p>竞争分析</p>"},

  "greenblatt_ranking": [
    {"layer": "L1", "dimension": "从上表取", "metric": "从上表取", "value": "从上表取", "weight": "从上表取", "rank": "从上表取", "verdict": "基于排名写判断"},
    {"layer": "L2", "dimension": "从上表取", "metric": "从上表取", "value": "从上表取", "weight": "从上表取", "rank": "从上表取", "verdict": "基于排名写判断"},
    {"layer": "L3", "dimension": "从上表取", "metric": "从上表取", "value": "从上表取", "weight": "从上表取", "rank": "从上表取", "verdict": "基于排名写判断"},
    {"layer": "L4", "dimension": "从上表取", "metric": "从上表取", "value": "从上表取", "weight": "从上表取", "rank": "从上表取", "verdict": "基于排名写判断"}
  ],
  "ranking_summary": "从上表取",
  "composite_score": 0.0,
  "composite_rank_8": "从上表取",
  "layer_weights": {"L1": "40%", "L2": "25%", "L3": "25%", "L4": "10%"},

  "f_score_items": [
    {"group": "盈利", "criterion": "ROA > 0", "score": 0, "reason": "如果有数据支撑就填, 没有就标记不确定"},
    ...
  ],
   "f_score_total": "0",

  "dashboard_metrics": [
    {"label": "营收增速", "value": "从上表取", "note": "YoY"},
    {"label": "Beta", "value": "从上表取", "note": ""},
    {"label": "FCF Yield", "value": "从上表取", "note": ""},
    {"label": "ROIC", "value": "从上表取", "note": ""}
  ],

  "s5_body_html": "<p>估值分析描述</p>",
  "s5_valuation_methods": [
    {"name": "DCF保守", "value": "$", "probability": "30%"},
    {"name": "DCF基准", "value": "$", "probability": "50%"},
    {"name": "DCF乐观", "value": "$", "probability": "20%"}
  ],

  "s6_body_html": "<p>未来展望</p>",
  "s6_scenarios": [
    {"scenario": "悲观", "probability": "25%", "price_target": "$", "return_pct": "", "description": ""},
    {"scenario": "基准", "probability": "50%", "price_target": "$", "return_pct": "", "description": ""},
    {"scenario": "乐观", "probability": "25%", "price_target": "$", "return_pct": "", "description": ""}
  ],

  "s7_risks": [
    {"risk": "", "probability": "高/中/低", "impact": "", "mitigation": ""}
  ],

  "s8_signal": {
    "signal": "BULLISH/NEUTRAL/BEARISH",
    "confidence": "HIGH/MEDIUM/LOW",
    "horizon": "MEDIUM",
    "action": "BUY/HOLD/SELL",
    "conviction": "STRONG/MODERATE/WEAK",
    "rank_summary": "加权综合分 X.XX, #X/8",
    "composite_rank": "从上表取"
  },

  "charts": [
    {"chart_id": "priceChart", "chart_type": "line", "section_id": "s3",
     "labels": ["25.01","25.03","25.05","25.07","25.09","25.11","26.01","26.03","26.05"],
     "datasets": [{"label": "股价", "data": [这里填合理趋势数据], "color": "#2563eb", "fill": true, "tension": 0.3}],
     "y_axis_label": "$", "y_axis_format": "$"},
    {"chart_id": "valuationRadar", "chart_type": "radar", "section_id": "s5",
     "labels": ["EBIT/EV","ROIC","F-Score","PEG","FCF质量","护城河","盈利稳定性"],
     "datasets": [{"label": "评分", "data": [排名映射0-100], "color": "#2563eb"}]},
    {"chart_id": "peerCompareChart", "chart_type": "bar", "section_id": "s5",
     "labels": ["NVDA","AMD","INTC","MU","行业均值"],
     "datasets": [{"label": "Forward PE", "data": [从上表取], "point_background_colors": ["#2563eb","#f97316","#8b5cf6","#10b981","#94a3b8"]}]},
    {"chart_id": "dcfChart", "chart_type": "bar", "section_id": "s5",
     "labels": ["当前价","悲观","基准","乐观"],
     "datasets": [{"label": "目标价", "data": [当前价,悲观,基准,乐观], "point_background_colors": ["#d97706","#dc2626","#d97706","#059669"]}]},
    {"chart_id": "scenarioChart", "chart_type": "bar", "section_id": "s6",
     "labels": ["悲观(25%)","基准(50%)","乐观(25%)"],
     "datasets": [{"label": "预期回报%", "data": [-X,+Y,+Z], "point_background_colors": ["#dc2626","#d97706","#059669"]}],
     "y_axis_label": "%", "y_axis_format": "%", "tooltip_prefix": "", "tooltip_suffix": "%"}
  ],

  "verdict": {
    "title": "最终裁决",
    "bull_points": ["基于 L2/L4 优势写"],
    "bear_points": ["基于 L1/L3 劣势写"],
    "composite_rank": "从上表取",
    "f_score_total": "从上表取",
    "recommendation": "买入/谨慎/观望",
    "rec_class": "bull/neut/bear"
  },

  "sidebar_dots": {"s1": "bull/neut/bear", ...},
  "overrides": [],
  "footer_text": "InvestSkill v3.0 · 教育性分析，不构成投资建议"
}
"""


def run_llm_with_real_data(report: StockReport, real_data_prompt: str,
                           logger: logging.Logger, use_opencode_llm: bool = False) -> StockReport:
    """调用 LLM, 注入真实数据 — 无 SCHEMA_HINT 污染"""
    from langchain_openai import ChatOpenAI

    from stock_analysis.reports.config import get_llm_config

    t0 = time.time()

    # 检查是否使用 OpenCode LLM IPC 模式
    opencode_client = None
    if use_opencode_llm:
        from stock_analysis.llm_client import create_llm_client
        opencode_client = create_llm_client(use_opencode=True)
        if opencode_client:
            logger.info("  使用 OpenCode LLM IPC 模式（通过文件 + stdout 标记）")
        else:
            logger.warning("  --use-opencode-llm 已启用但环境不支持，fallback 到直接 API")

    if not opencode_client:
        cfg = get_llm_config()
        llm = ChatOpenAI(
            model=cfg["model"],
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            temperature=0.1,
        )

    is_crypto = report.asset_category == AssetCategory.CRYPTO
    is_pos = report.ticker in {'ETH', 'SOL', 'BNB'}
    is_btc = report.ticker == 'BTC'

    # 加密资产排名体系说明
    if is_pos:
        ranking_system = """
## PoS 加密四层加权排名体系

| Layer | 指标 | 权重 | 说明 |
|-------|------|:---:|------|
| L1 | MCap/TVL | 40% | 便不便宜 (越低越好) |
| L2 | Staking比率 | 25% | 网络安全性 (越高越好) |
| L3 | Crypto F-Score (0-6) | 25% | 链上健康度 (越高越好) |
| L4 | 年通胀率 | 10% | 供给压力 (越低越好) |

综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10 | 越小越好

⚠️ Crypto F-Score (0/6) 与 Piotroski F-Score (0/9) 是完全不同的体系。加密资产没有传统财报数据，f_score_items 全部填 score=0, reason="数据不足（加密资产无传统财报）"。verdict.f_score_total 写 Crypto F-Score 的值（字符串类型如 "X/6"）。根级 f_score_total 写纯数字字符串（如 "6"）。
"""
    elif is_btc:
        ranking_system = """
## BTC 加密四层加权排名体系

| Layer | 指标 | 权重 | 说明 |
|-------|------|:---:|------|
| L1 | MVRV Z-Score | 40% | 便不便宜 (越低越便宜) |
| L2 | Hash Rate (EH/s) | 25% | 网络安全性 (越高越强) |
| L3 | 改编 F-Score (链上) | 25% | 链上健康度 (0-9) |
| L4 | 距下次减半天数 | 10% | 周期位置 (越近越好) |

综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10 | 越小越好

⚠️ BTC 无传统财报，f_score_items 如无数据支撑则 score=0, reason="数据不足（BTC 无传统财报）"。
"""
    else:
        ranking_system = """
## 四层加权排名体系

| Layer | 指标 | 权重 | 说明 |
|-------|------|:---:|------|
| L1 | EBIT/EV | 40% | 便不便宜 |
| L2 | ROIC | 25% | 赚不赚钱 |
| L3 | F-Score | 25% | 会不会崩 |
| L4 | PEG | 10% | 增长值不值 |

综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10 | 越小越好
"""

    prompt = f"""你是专业投资分析师。为 {report.company_name} ({report.ticker}, {report.company_name_en}) 生成完整 StockReport JSON。

基本信息:
- 交易所: {report.exchange}
- 行业: {report.sector}
- 资产类别: {report.asset_category.value}
- 日期: 2026-05-11

{ranking_system}

{real_data_prompt}

---

## 输出格式

{OUTPUT_SCHEMA}

## 最后提醒

- 数值字段（价格、PE、排名、分数等）从上方真实数据区块复制，禁止用训练记忆覆盖
- 叙述字段（竞争格局、风险矩阵、展望等）基于真实数据分析，可以发挥判断力
- **禁止在叙述中提及排名位置（如"排名第4/7"、"L1排名第1"等），排名已移至 index.html 统一展示**
- F-Score 9 项逐条: 如果某条没有足够数据支撑, score 填 0, reason 写 "数据不足"
- 图表数据: 基于上方真实数据构造合理的趋势/对比"""
    if is_pos:
        prompt += """
- **加密资产特殊规则**: f_score_total 写 Crypto F-Score (0-6) 数值，不是 Piotroski (0-9)
- verdict.f_score_total 格式: "X/6 (Crypto F-Score)" 而不是 "X/9"
- cover_kpi 的 EBIT/EV 改为 MCap/TVL, ROIC 改为 Staking率"""
    prompt += """

只返回 JSON，不要 markdown 代码块包裹。
"""
    if opencode_client:
        logger.info(f"  OpenCode LLM 请求: prompt={len(prompt):,} chars")
    else:
        logger.info(f"  LLM 请求: model={cfg['model']}, prompt={len(prompt):,} chars")
    logger.info(f"  注入真实数据: {len(real_data_prompt):,} chars")

    try:
        if opencode_client:
            content = opencode_client.invoke(prompt, model="deepseek-v4-pro", temperature=0.1)
            elapsed = time.time() - t0
            logger.info(f"  OpenCode LLM 响应: {elapsed:.1f}s, length={len(content):,} chars")
        else:
            response = llm.invoke(prompt, timeout=300)
            elapsed = time.time() - t0
            token_usage = getattr(response, 'response_metadata', {})
            logger.info(f"  LLM 响应: {elapsed:.1f}s, tokens={token_usage}")
            content = response.content.strip()
            logger.info(f"  原始响应长度: {len(content):,} chars")

        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else parts[0]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        result = StockReport.model_validate_json(content)
        result.company_dir = report.company_dir
        result.module_states = report.module_states
        for m in result.module_states.values():
            m.status = ModuleStatus.FILLED
        logger.info(f"  解析成功: {len(result.charts)} charts, {len(result.f_score_items)} F-Score")
        return result
    except Exception as e:
        logger.error(f"  LLM 失败 ({type(e).__name__}, {time.time()-t0:.1f}s): {str(e)[:500]}")
        return report


def run_analysis(company_name: str, dry_run: bool = False, use_opencode_llm: bool = False) -> Optional[str]:
    """运行完整分析流程

    Args:
        company_name: 公司中文名 (如 "英特尔")
        dry_run: 只 fetch+rank, 不调用 LLM

    Returns:
        生成的 HTML 路径, 或 None
    """
    logger = build_logger(company_name)
    t_total = time.time()

    logger.info(f"{'='*60}")
    logger.info(f"Pipeline 启动: {company_name}")
    logger.info(f"{'='*60}")

    # Stage 0: Scaffold
    logger.info("[Stage 0: scaffold]")
    report = scaffold(company_name)
    logger.info(f"  Ticker={report.ticker}, Exchange={report.exchange}, Asset={report.asset_category.value}")

    # Stage 0.5: Auto-refresh prices.json before analysis
    logger.info("[Stage 0.5: refresh] 分析前自动刷新 prices.json 缓存")
    try:
        from stock_analysis.data.fetcher import sync_public_data_to_json
        sync_public_data_to_json(logger=logger)
        logger.info("  ✅ 缓存刷新完成")
    except Exception as e:
        logger.warning(f"  ⚠️ 缓存刷新失败: {e}，继续使用旧缓存")

    # Stage 1: Fetch real data for ALL 8
    logger.info("[Stage 1: fetch] 按多市场数据源矩阵加载缓存/实时数据")
    prices = fetch_all_8(logger=logger)
    ticker = report.ticker
    my_data = prices.get(ticker)
    if not my_data:
        if ticker in {'BTC', 'ETH', 'SOL', 'BNB'}:
            fresh_crypto = fetch_crypto_public([ticker], logger=logger)
            prices.update(fresh_crypto)
        else:
            yf_symbol = yfinance_symbol_for_ticker(ticker)
            fresh_equity = fetch_yfinance([yf_symbol], logger=logger)
            prices.update(fresh_equity)
        my_data = prices.get(ticker)
    if my_data:
        logger.info(f"  {ticker}: price={my_data.price}, PE={my_data.pe_ratio}, PEG={my_data.peg_ratio}")
    else:
        logger.warning(f"  {ticker}: 未抓取到数据")

    # Stage 2: Rank (pure math)
    logger.info("[Stage 2: rank] 纯数学四层加权排名")

    all_ebit_ev = {}
    all_roic = {}
    all_f_score = {}
    all_peg = {}
    for t, p in prices.items():
        if p.ebit_ev_num is not None:
            all_ebit_ev[t] = p.ebit_ev_num
        if p.roic_num is not None:
            all_roic[t] = p.roic_num
        if p.f_score is not None:
            all_f_score[t] = p.f_score
        if p.peg_num is not None:
            all_peg[t] = p.peg_num

    rankable_tickers = {t for t in prices if has_report_for_ticker(t)}
    rankable_tickers.add(ticker)
    rankings = {}
    for t in prices:
        if t == 'BTC':
            # BTC 专用排名
            btc = prices.get('BTC')
            if btc and btc.mvrv_z_score:
                all_mvrv = {'BTC': btc.mvrv_z_score}
                all_hash = {'BTC': btc.hash_rate_eh}
                all_btc_f = {'BTC': btc.f_score}
                all_halving = {'BTC': btc.days_since_halving}
                result = compute_crypto_ranking(
                    btc.mvrv_z_score, btc.hash_rate_eh,
                    btc.f_score, btc.days_since_halving,
                    all_mvrv, all_hash, all_btc_f, all_halving,
                )
                if t in rankable_tickers:
                    rankings[t] = result
                logger.info(f"  BTC: composite={result.composite_score:.2f}")
        elif t in {'ETH', 'SOL', 'BNB'}:
            pos = prices.get(t)
            all_mcap_tvl = {k: v.mcap_tvl_ratio for k, v in prices.items() if k in {'ETH', 'SOL', 'BNB'} and v.mcap_tvl_ratio is not None}
            all_staking = {k: v.staking_ratio for k, v in prices.items() if k in {'ETH', 'SOL', 'BNB'} and v.staking_ratio is not None}
            all_crypto_f = {k: v.f_score for k, v in prices.items() if k in {'ETH', 'SOL', 'BNB'} and v.f_score is not None}
            all_inflation = {k: v.supply_inflation for k, v in prices.items() if k in {'ETH', 'SOL', 'BNB'} and v.supply_inflation is not None}
            if pos and all_mcap_tvl and all_staking and all_crypto_f and all_inflation:
                result = compute_pos_crypto_ranking(
                    t,
                    pos.mcap_tvl_ratio,
                    pos.staking_ratio,
                    pos.f_score,
                    pos.supply_inflation,
                    all_mcap_tvl,
                    all_staking,
                    all_crypto_f,
                    all_inflation,
                )
                if t in rankable_tickers:
                    rankings[t] = result
                logger.info(f"  {t}: composite={result.composite_score:.2f}")
        elif t in all_ebit_ev:
            result = compute_greenblatt(
                t,
                all_ebit_ev.get(t),
                all_roic.get(t),
                all_f_score.get(t),
                all_peg.get(t),
                all_ebit_ev, all_roic, all_f_score, all_peg,
            )
            if t in rankable_tickers:
                rankings[t] = result
            if t == ticker:
                logger.info(f"  {t}: composite={result.composite_score:.2f}, rank={result.composite_rank}")

    apply_cross_asset_scores(prices, rankings)

    if dry_run:
        logger.info("Dry run — 跳过 LLM 生成")
        return None

    # Stage 3: LLM with real data
    logger.info("[Stage 3: LLM] 注入真实数据生成报告")
    real_data_prompt = build_real_data_prompt(company_name, report.ticker, prices, rankings)
    report = run_llm_with_real_data(report, real_data_prompt, logger, use_opencode_llm=use_opencode_llm)

    # LLM 失败检测: 如果 report 仍为空壳（无 charts、无 verdict），跳过 render
    charts = getattr(report, 'charts', None)
    company_overview = getattr(report, 'company_overview', None)
    if not charts and not company_overview:
        logger.error("  LLM 返回空报告，跳过 render。请检查 API 配置或网络连接。")
        return None

    report = apply_authoritative_report_data(report, my_data, rankings.get(ticker), prices, logger)
    report = apply_real_price_history(report, my_data, logger)

    # Stage 4: Render
    logger.info("[Stage 4: render] 生成 HTML")
    today = datetime.now().strftime('%y%m%d')
    output_dir = BASE_DIR / '分析输出' / company_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{today}_综合分析报告.html'
    html_path = render_to_file(report, str(output_path), logger=logger)

    # Stage 5: Validate
    logger.info("[Stage 5: validate] HTML 完整性检查")
    from stock_analysis.reports.stages.validate import validate
    passed, issues = validate(report, html_path)
    logger.info(f"  通过: {'是' if passed else '否'}")
    for i in issues:
        logger.info(f"  [{i}]")

    try:
        from stock_analysis.generator import regenerate
        regenerate()
        logger.info('[Stage 6: index] index.html 已根据分析输出重建')
    except Exception as e:
        logger.warning(f'[Stage 6: index] index.html 重建失败: {e}')

    total_elapsed = time.time() - t_total
    logger.info(f"{'='*60}")
    logger.info(f"总耗时: {total_elapsed:.1f}s")
    logger.info(f"HTML: {html_path}")
    logger.info(f"{'✅ 完成' if passed else '⚠️ 部分完成'}")
    logger.info(f"{'='*60}")

    return html_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python -m tools.pipeline <公司名> [--dry-run] [--use-opencode-llm]')
        print('      python -m tools.pipeline index     # 再生index.html')
        print('      python -m tools.pipeline watch     # 监听分析输出并自动重建index.html')
        print('      python -m tools.pipeline validate <报告路径>')
        print('')
        print('选项:')
        print('  --dry-run             不调用 LLM，仅验证数据流')
        print('  --use-opencode-llm    通过 IPC 调用 OpenCode Agent 的 LLM（而非直接 API）')
        sys.exit(1)
    if sys.argv[1] == 'index':
        from stock_analysis.generator import regenerate
        regenerate()
        sys.exit(0)
    if sys.argv[1] == 'watch':
        logger = build_logger('watch-index')
        try:
            watch_report_outputs(logger=logger)
        except KeyboardInterrupt:
            logger.info('[watch] 已停止监听')
        sys.exit(0)
    if sys.argv[1] == 'validate':
        if len(sys.argv) < 3:
            print('用法: python -m tools.pipeline validate <报告路径>')
            sys.exit(1)
        from stock_analysis.reports.stages.validate import validate
        html_path = sys.argv[2]
        passed, issues = validate(None, html_path)
        print('✅ 通过' if passed else '❌ 未通过')
        for i in issues:
            print(f'  {i}')
        sys.exit(0 if passed else 1)
    company = sys.argv[1]
    dry = '--dry-run' in sys.argv
    use_opencode = '--use-opencode-llm' in sys.argv
    run_analysis(company, dry_run=dry, use_opencode_llm=use_opencode)
