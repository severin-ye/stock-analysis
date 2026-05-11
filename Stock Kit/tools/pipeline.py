"""编排器: fetch → rank → LLM(仅文本) → render → validate

工具与 InvestSkill 的联动:
  1. fetcher 按 InvestSkill 指定的数据源 (marketbeat/trefis) 抓取
  2. ranker 实现 InvestSkill 四层加权排名公式 (纯数学)
  3. 真实数据注入 LLM prompt (LLM 只生成叙述文本)
  4. renderer 使用 InvestSkill 的 Jinja2 模板
  5. validator 检查 HTML 完整性
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'InvestSkill'))

from report_engine.schema import StockReport, ModuleStatus, AssetCategory, ChartType, ChartDef, ChartDataset
from report_engine.stages.scaffold import scaffold
from report_engine.stages.render import render_to_file
from report_engine.stages.validate import validate

from tools.fetcher import fetch_all_8, PriceSnapshot, TICKER_MAP
from tools.ranker import compute_greenblatt, compute_crypto_ranking, RankingResult

BASE_DIR = Path('/home/severin/Codelib/股市分析')
LOG_DIR = BASE_DIR / '.sisyphus' / 'pipeline_logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)


def build_logger(company_name: str) -> logging.Logger:
    log_filename = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{company_name}.log"
    logger = logging.getLogger(f'pipeline.{company_name}')
    logger.setLevel(logging.DEBUG)

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


def build_real_data_prompt(company_name: str, ticker: str, prices: dict[str, PriceSnapshot],
                           rankings: dict[str, RankingResult]) -> str:
    """构建完整真实数据注入块"""
    info = prices.get(ticker)
    rank = rankings.get(ticker)
    if not info:
        return ""

    name_map = {'NVDA': '英伟达', 'AAPL': '苹果', 'INTC': '英特尔', 'TSLA': '特斯拉',
                'AMD': 'AMD', 'MU': '美光', '1810.HK': '小米', 'BTC': '比特币'}

    lines = [f"""
## ⚠️ 反幻觉规则 — 必须遵守

1. **所有数值必须来自下方真实数据区块。禁止使用训练数据中的任何数字。**
2. **如果下方区块没有某数字，留空或用 "—" 标记，不要编造。**
3. **排名结果已预计算，禁止修改 layer/rank/value/composite_score。**
4. **叙述和分析可以发挥判断力，但引用的数字必须是下方的。**

---
## 真实采集数据 (stockanalysis.com + marketbeat.com 交叉验证, {datetime.now().strftime('%Y-%m-%d')})

### 全部 8 家标的数据

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
计算: {rank.summary}
""")

    # 全部 8 家排名汇总
    if rankings:
        lines.append("""
### 全部 8 家四层排名汇总 (纯数学, 禁止修改)

| 标的 | L1(EBIT/EV) | L2(ROIC) | L3(F-Score) | L4(PEG) | 综合分 | 综合排名 |
|------|------------|----------|-------------|---------|--------|----------|
""")
        sorted_ranks = sorted([(t, r.composite_score, r.composite_rank) for t, r in rankings.items()], key=lambda x: x[1])
        for t, score, c_rank in sorted_ranks:
            nm = name_map.get(t, t)
            rows = rankings[t].rows
            l1 = f"{rows[0].value}({rows[0].rank})"
            l2 = f"{rows[1].value}({rows[1].rank})"
            l3 = f"{rows[2].value}({rows[2].rank})"
            l4 = f"{rows[3].value}({rows[3].rank})"
            lines.append(f"| {nm} | {l1} | {l2} | {l3} | {l4} | {score:.2f} | {c_rank} |")

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
  "f_score_total": 0,

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
                           logger: logging.Logger) -> StockReport:
    """调用 LLM, 注入真实数据 — 无 SCHEMA_HINT 污染"""
    from langchain_openai import ChatOpenAI
    from InvestSkill.report_engine.config import get_deepseek_config

    t0 = time.time()
    cfg = get_deepseek_config()
    llm = ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=0.1,
    )

    prompt = f"""你是专业投资分析师。为 {report.company_name} ({report.ticker}, {report.company_name_en}) 生成完整 StockReport JSON。

基本信息:
- 交易所: {report.exchange}
- 行业: {report.sector}
- 资产类别: {report.asset_category.value}
- 日期: 2026-05-11

## 四层加权排名体系

| Layer | 指标 | 权重 | 说明 |
|-------|------|:---:|------|
| L1 | EBIT/EV | 40% | 便不便宜 |
| L2 | ROIC | 25% | 赚不赚钱 |
| L3 | F-Score | 25% | 会不会崩 |
| L4 | PEG | 10% | 增长值不值 |

综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10 | 越小越好

{real_data_prompt}

---

## 输出格式

{OUTPUT_SCHEMA}

## 最后提醒

- 数值字段（价格、PE、排名、分数等）从上方真实数据区块复制，禁止用训练记忆覆盖
- 叙述字段（竞争格局、风险矩阵、展望等）基于真实数据分析，可以发挥判断力
- **禁止在叙述中提及排名位置（如"排名第4/7"、"L1排名第1"等），排名已移至 index.html 统一展示**
- F-Score 9 项逐条: 如果某条没有足够数据支撑, score 填 0, reason 写 "数据不足"
- 图表数据: 基于上方真实数据构造合理的趋势/对比

只返回 JSON，不要 markdown 代码块包裹。
"""
    logger.info(f"  LLM 请求: model={cfg['model']}, prompt={len(prompt):,} chars")
    logger.info(f"  注入真实数据: {len(real_data_prompt):,} chars")

    try:
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


def run_analysis(company_name: str, dry_run: bool = False) -> Optional[str]:
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

    # Stage 1: Fetch real data for ALL 8
    logger.info("[Stage 1: fetch] 从 marketbeat.com + trefis.com 抓取 8 家数据")
    prices = fetch_all_8(logger=logger)
    ticker = report.ticker
    my_data = prices.get(ticker)
    if my_data:
        logger.info(f"  {ticker}: price={my_data.price}, PE={my_data.pe_ratio}, PEG={my_data.peg_ratio}")
    else:
        logger.warning(f"  {ticker}: 未抓取到数据")

    # Stage 2: Rank (pure math)
    logger.info(f"[Stage 2: rank] 纯数学四层加权排名")

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
                rankings[t] = result
                logger.info(f"  BTC: composite={result.composite_score:.2f}")
        elif t in all_ebit_ev:
            result = compute_greenblatt(
                t,
                all_ebit_ev.get(t),
                all_roic.get(t),
                all_f_score.get(t),
                all_peg.get(t),
                all_ebit_ev, all_roic, all_f_score, all_peg,
            )
            rankings[t] = result
            if t == ticker:
                logger.info(f"  {t}: composite={result.composite_score:.2f}, rank={result.composite_rank}")

    if dry_run:
        logger.info("Dry run — 跳过 LLM 生成")
        return None

    # Stage 3: LLM with real data
    logger.info("[Stage 3: LLM] 注入真实数据生成报告")
    real_data_prompt = build_real_data_prompt(company_name, report.ticker, prices, rankings)
    report = run_llm_with_real_data(report, real_data_prompt, logger)

    # Stage 4: Render
    logger.info("[Stage 4: render] 生成 HTML")
    today = datetime.now().strftime('%y%m%d')
    output_path = BASE_DIR / company_name / f'{today}_综合分析报告.html'
    html_path = render_to_file(report, str(output_path), logger=logger)

    # Stage 5: Validate
    logger.info("[Stage 5: validate] HTML 完整性检查")
    from tools.validator import validate_html_file
    passed, issues = validate_html_file(html_path)
    logger.info(f"  通过: {'是' if passed else '否'}")
    for i in issues:
        logger.info(f"  [{i}]")

    total_elapsed = time.time() - t_total
    logger.info(f"{'='*60}")
    logger.info(f"总耗时: {total_elapsed:.1f}s")
    logger.info(f"HTML: {html_path}")
    logger.info(f"{'✅ 完成' if passed else '⚠️ 部分完成'}")
    logger.info(f"{'='*60}")

    return html_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python -m tools.pipeline <公司名> [--dry-run]')
        sys.exit(1)
    company = sys.argv[1]
    dry = '--dry-run' in sys.argv
    run_analysis(company, dry_run=dry)
