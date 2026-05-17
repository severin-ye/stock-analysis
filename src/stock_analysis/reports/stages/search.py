"""Stage 1+2: 一站式生成 (搜索 + 分析合并) — 四层加权排名"""


import logging

from langchain_openai import ChatOpenAI

from tools.runtime.report_engine.config import get_llm_config
from tools.runtime.report_engine.schema import ModuleStatus, StockReport

SCHEMA_HINT = """
必须返回的 JSON 结构，所有字段名必须精确匹配（数值从上文真实数据区块取，此处仅为格式示例）:

{
  "ticker": "TICKER", "company_name": "公司中文名", "company_name_en": "English Name",
  "exchange": "NASDAQ", "sector": "行业", "asset_category": "stock",
  "report_date": "2026-05-11", "data_date": "2026-05-10 收盘",
  "cover_title": "TICKER — 公司名 综合投资分析",
  "cover_price": "从上表取",
  "cover_market_cap": "从上表取",

  "cover_kpi": [
    {"label":"当前股价","value":"从上表取","css_class":"up/dn"},
    {"label":"YTD","value":"从上表取","css_class":"up/dn"},
    {"label":"52周范围","value":"从上表取","sub":"高位/低位/中位"},
    {"label":"Forward P/E","value":"从上表取"},
    {"label":"EBIT/EV","value":"从上表取"},
    {"label":"ROIC","value":"从上表取"}
  ],

  "s1_price_changes": [
    {"dimension":"1日","change_pct":"从上表取","corresponding_price":"","probability_weight":"—","industry_compare":""},
    {"dimension":"1周","change_pct":"从上表取","corresponding_price":"","probability_weight":"—","industry_compare":""},
    {"dimension":"YTD","change_pct":"从上表取","corresponding_price":"","probability_weight":"—","industry_compare":""},
    {"dimension":"1年","change_pct":"从上表取","corresponding_price":"","probability_weight":"—","industry_compare":""},
    {"dimension":"52周极端","change_pct":"","corresponding_price":"","probability_weight":"—","industry_compare":""}
  ],
  "s1_core_judgment": "基于排名结果的一句话总结",

  "s2": {"title":"🏢 公司概览","subtitle":"","body_html":"<p>...</p>","key_metrics":[{"label":"市值","value":"从上表取","note":""}]},

  "s3_body_html": "<p>过去一年走势描述</p>",

  "s4": {"title":"⚔️ 竞争格局","subtitle":"","body_html":"<p>...</p>"},

  "greenblatt_ranking": [
    {"layer":"L1","dimension":"💰 便不便宜","metric":"EBIT/EV","value":"从上表取","weight":"40%","rank":"从上表取","verdict":"基于排名写判断"},
    {"layer":"L2","dimension":"🏭 赚不赚钱","metric":"ROIC","value":"从上表取","weight":"25%","rank":"从上表取","verdict":"基于排名写判断"},
    {"layer":"L3","dimension":"🛡️ 会不会崩","metric":"F-Score","value":"从上表取","weight":"25%","rank":"从上表取","verdict":"基于排名写判断"},
    {"layer":"L4","dimension":"📈 增长值不值","metric":"PEG","value":"从上表取","weight":"10%","rank":"从上表取","verdict":"基于排名写判断"}
  ],
  "ranking_summary": "从上表取",
  "composite_score": 0.0,
  "composite_rank_8": "从上表取",
  "layer_weights": {"L1":"40%","L2":"25%","L3":"25%","L4":"10%"},

  "f_score_items": [
    {"group":"盈利","criterion":"ROA > 0","score":0,"reason":"数据不足则 score=0"},
    {"group":"盈利","criterion":"CFO > 0","score":0,"reason":""},
    {"group":"盈利","criterion":"ΔROA > 0","score":0,"reason":""},
    {"group":"盈利","criterion":"CFO > NI","score":0,"reason":""},
    {"group":"杠杆","criterion":"ΔLeverage < 0","score":0,"reason":""},
    {"group":"杠杆","criterion":"ΔLiquidity > 0","score":0,"reason":""},
    {"group":"杠杆","criterion":"无增发","score":0,"reason":""},
    {"group":"效率","criterion":"ΔMargin > 0","score":0,"reason":""},
    {"group":"效率","criterion":"ΔTurnover > 0","score":0,"reason":""}
  ],
  "f_score_total": "0",

  "dashboard_metrics": [
    {"label":"营收增速","value":"从上表取","note":"YoY"},
    {"label":"毛利率","value":"从上表取","note":""},
    {"label":"FCF利润率","value":"从上表取","note":""},
    {"label":"研发占比","value":"从上表取","note":""},
    {"label":"负债率","value":"从上表取","note":""},
    {"label":"股息率","value":"从上表取","note":""},
    {"label":"Beta","value":"从上表取","note":""},
    {"label":"PEG(Fwd)","value":"从上表取","note":""}
  ],

  "s5_body_html": "<p>估值分析描述</p>",
  "s5_valuation_methods": [
    {"name":"DCF保守","value":"$","probability":"30%"},
    {"name":"DCF基准","value":"$","probability":"50%"},
    {"name":"DCF乐观","value":"$","probability":"20%"}
  ],

  "s6_body_html": "<p>未来展望</p>",
  "s6_scenarios": [
    {"scenario":"悲观","probability":"25%","price_target":"$","return_pct":"","description":""},
    {"scenario":"基准","probability":"50%","price_target":"$","return_pct":"","description":""},
    {"scenario":"乐观","probability":"25%","price_target":"$","return_pct":"","description":""}
  ],

  "s7_risks": [
    {"risk":"","probability":"高/中/低","impact":"","mitigation":""}
  ],

  "s8_signal": {
    "signal":"BULLISH/NEUTRAL/BEARISH",
    "confidence":"HIGH/MEDIUM/LOW",
    "horizon":"SHORT/MEDIUM/LONG",
    "action":"BUY/HOLD/SELL",
    "conviction":"STRONG/MODERATE/WEAK",
    "rank_summary":"从上表取",
    "composite_rank":"从上表取"
  },

  "charts": [
    {"chart_id":"priceChart","chart_type":"line","section_id":"s3","labels":["月1","月2","月3","月4","月5","月6","月7","月8"],"datasets":[{"label":"TICKER","data":[0,0,0,0,0,0,0,0],"color":"#2563eb","fill":true,"tension":0.3,"point_radius":3}],"y_axis_label":"$","y_axis_format":"$"},
    {"chart_id":"valuationRadar","chart_type":"radar","section_id":"s5","labels":["DCF安全边际","P/E vs 行业","EV/EBITDA","PEG","ROIC vs WACC","利润率","FCF质量","护城河","F-Score","资产负债","盈利稳定性"],"datasets":[{"label":"TICKER","data":[0,0,0,0,0,0,0,0,0,0,0],"color":"#2563eb"}]},
    {"chart_id":"peerCompareChart","chart_type":"bar","section_id":"s5","labels":["标的1","标的2","标的3","标的4","行业均值"],"datasets":[{"label":"Forward PE","data":[0,0,0,0,0],"point_background_colors":["#2563eb","#f97316","#8b5cf6","#10b981","#94a3b8"]}]},
    {"chart_id":"dcfChart","chart_type":"bar","section_id":"s5","labels":["当前价","悲观","基准","乐观"],"datasets":[{"label":"目标价","data":[0,0,0,0],"point_background_colors":["#d97706","#dc2626","#d97706","#059669"]}]},
    {"chart_id":"scenarioChart","chart_type":"bar","section_id":"s6","labels":["悲观(25%)","基准(50%)","乐观(25%)"],"datasets":[{"label":"预期回报%","data":[0,0,0],"point_background_colors":["#dc2626","#d97706","#059669"]}],"y_axis_label":"%","y_axis_format":"%","tooltip_prefix":"","tooltip_suffix":"%"}
  ],

  "verdict": {
    "title":"最终裁决",
    "bull_points":[],
    "bear_points":[],
    "composite_rank":"从上表取",
    "f_score_total":"从上表取",
    "recommendation":"BUY/HOLD/SELL",
    "rec_class":"bull/bear/neut"
  },

  "sidebar_dots": {"s1":"bull","s3":"bull","s4":"bull","s5":"neut","s6":"bull","s7":"neut","s8":"bull"},
  "overrides": [],
  "footer_text": "InvestSkill v3.0 · 教育性分析，不构成投资建议 · 排名分母/11"
}
"""


def run_search(report: StockReport, logger=None) -> StockReport:
    raise RuntimeError(
        "report_engine.stages.search 已禁用：该旧入口没有真实数据采集，禁止用 LLM 生成完整数值报告。"
        "请使用: PYTHONPATH='stock_kit' python3 -m tools.pipeline <公司名>"
    )

    import time
    t0 = time.time()

    cfg = get_llm_config()
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

## 四层加权排名体系 (深度价值导向)

所有投资标的一起排名: NVDA(英伟达), AAPL(苹果), TSLA(特斯拉), INTC(英特尔), AMD, MU(美光), 小米(1810.HK), BTC(比特币), SK海力士(000660.KS), 三星电子(005930.KS), 三星生物制药(207940.KS), 现代汽车(005380.KS), 博通(AVGO), LLY(礼来)。共14家。
排名范围严格 #1~14/14 (#1=最好, #14=最差)。禁止用其他分母!

| Layer | 指标 | 权重 | 说明 |
|-------|------|:---:|------|
| L1 | EBIT/EV | 40% | 便不便宜。深度价值核心。 |
| L2 | ROIC | 25% | 赚不赚钱。排除价值陷阱。 |
| L3 | F-Score | 25% | 会不会崩。安全底线(避坑)。 |
| L4 | PEG | 10% | 增长值不值。权重最低。 |

综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10 | 越小越好

## BTC/加密适配
BTC 不适用传统财务指标，改为:
- L1: MVRV Z-Score (当前约2.46, 越低越便宜, 历史顶部>7)
- L2: 网络强度 (算力957EH/s + ETF AUM ~$100B + 采用率)
- L3: 减半周期位置 (距2028减半约18个月, 历史减半后12-18月达新高)
- L4: 改编F-Score (链上指标: 活跃地址/哈希率趋势/交易所余额/NVT等)

## 小米/港股适配
- 正常用 EBIT/EV + ROIC + PEG + F-Score
- 标注 "港股财报，Non-GAAP Forward Estimate"
- 排名与其他家统一对比

## 三星电子/韩股适配
- 三星电子 (005930.KS, KRX KOSPI) 正常用 EBIT/EV + ROIC + PEG + F-Score
- 三星是全球最大半导体+消费电子综合企业 (DRAM 40%+市占, NAND 35%+, 手机 #1)
- 财务数据基于 KRW 万亿单位，市值约 350万亿韩元 (~$2,500亿)
- 标注 "韩股 K-IFRS 财报, 可能存在 IFRS vs US GAAP 差异"
- 排名与其他 9 家统一对比 (共 10 家)

## 数据要求
1. 搜索真实数据: 股价、市值、PE、EBIT、EV、ROIC、PEG、FCF
2. 计算四层排名，必须4行 (L1-L4)
3. 计算 composite_score 和 composite_rank_8
4. F-Score 9项逐条打分 (必须9项, 0或1, 写reason)
5. 5张图表 (priceChart/valuationRadar/peerCompareChart/dcfChart/scenarioChart)
6. 所有8个section + verdict
7. 百分比用 +X%/-X%

{SCHEMA_HINT}

只返回 JSON，不要 markdown 代码块包裹。
"""
    log = logger or logging.getLogger('pipeline')
    log.info(f"  LLM 请求: model={cfg['model']}, base_url={cfg['base_url']}")
    log.info(f"  Prompt 长度: {len(prompt):,} chars")
    log.info("  等待 LLM 响应 (Deepseek V4 Pro 通常 60-180s)...")

    try:
        response = llm.invoke(prompt, timeout=300)
        elapsed_llm = time.time() - t0

        token_usage = getattr(response, 'response_metadata', {})
        log.info(f"  LLM 响应: {elapsed_llm:.1f}s, token_usage={token_usage}")

        content = response.content.strip()
        log.info(f"  原始响应长度: {len(content):,} chars")

        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else parts[0]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        log.info(f"  清理后 JSON 长度: {len(content):,} chars")

        result = StockReport.model_validate_json(content)
        result.company_dir = report.company_dir
        result.module_states = report.module_states
        for m in result.module_states.values():
            m.status = ModuleStatus.FILLED

        log.info(f"  解析成功: {len(result.charts)} charts, {len(result.f_score_items)} F-Score, composite={result.composite_rank_8}")
        log.info(f"  顶层字典 keys: {list(result.model_dump(mode='json').keys())}")
        return result
    except Exception as e:
        elapsed = time.time() - t0
        err_type = type(e).__name__
        log.error(f"  ⚠️ LLM 失败 ({err_type}, {elapsed:.1f}s): {str(e)[:500]}")
        if hasattr(e, '__traceback__'):
            import traceback
            log.debug(f"  Traceback: {traceback.format_exc()}")
        return report
