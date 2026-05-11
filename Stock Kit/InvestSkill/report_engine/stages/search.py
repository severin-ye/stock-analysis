"""Stage 1+2: 一站式生成 (搜索 + 分析合并) — 四层加权排名"""

from langchain_openai import ChatOpenAI
from report_engine.config import get_deepseek_config
from report_engine.schema import StockReport, ModuleStatus
import json

SCHEMA_HINT = """
必须返回的 JSON 结构，所有字段名必须精确匹配:

{
  "ticker": "NVDA", "company_name": "英伟达", "company_name_en": "NVIDIA",
  "exchange": "NASDAQ", "sector": "半导体", "asset_category": "stock",
  "report_date": "2026-05-11", "data_date": "2026-05-10 收盘",
  "cover_title": "NVDA — 英伟达 综合投资分析",
  "cover_price": "$191.48",
  "cover_market_cap": "$4.7万亿",

  "cover_kpi": [
    {"label":"当前股价","value":"$191.48","css_class":"up"},
    {"label":"YTD","value":"+35.2%","css_class":"up"},
    {"label":"52周范围","value":"$110-$210","sub":"高位"},
    {"label":"Forward P/E","value":"45.3x"},
    {"label":"EBIT/EV","value":"2.52%"},
    {"label":"ROIC","value":"55.5%"}
  ],

  "s1_price_changes": [
    {"dimension":"1日","change_pct":"+1.2%","corresponding_price":"$189→$191","probability_weight":"—","industry_compare":"板块+0.8%"},
    {"dimension":"1周","change_pct":"+3.5%","corresponding_price":"$185→$191","probability_weight":"—","industry_compare":"板块+2.1%"},
    {"dimension":"YTD","change_pct":"+35.2%","corresponding_price":"$141→$191","probability_weight":"—","industry_compare":"SOX +20.3%"},
    {"dimension":"1年","change_pct":"+118%","corresponding_price":"$87→$191","probability_weight":"—","industry_compare":"SOX +55.6%"},
    {"dimension":"52周极端","change_pct":"+73.6%","corresponding_price":"$110-$210 vs $191","probability_weight":"—","industry_compare":"高位区间"}
  ],
  "s1_core_judgment": "AI 投资周期仍在早期，Blackwell Ultra 2026H2 量产催化业绩，估值偏高但 PEG合理",

  "s2": {"title":"🏢 公司概览","subtitle":"AI 计算平台领导者","body_html":"<p>...</p>","key_metrics":[{"label":"市值","value":"$4.7万亿","note":"全球第二"}]},

  "s3_body_html": "<p>过去一年走势描述</p>",

  "s4": {"title":"⚔️ 竞争格局","subtitle":"GPU 双寡头","body_html":"<p>...</p>"},

  "greenblatt_ranking": [
    {"layer":"L1","dimension":"💰 便不便宜","metric":"EBIT/EV","value":"2.52%","weight":"40%","rank":"#3/8","verdict":"偏低但非极端折扣"},
    {"layer":"L2","dimension":"🏭 赚不赚钱","metric":"ROIC","value":"55.5%","weight":"25%","rank":"#1/8","verdict":"碾压级"},
    {"layer":"L3","dimension":"🛡️ 会不会崩","metric":"F-Score","value":"8/9","weight":"25%","rank":"#1/8","verdict":"财务极其健康"},
    {"layer":"L4","dimension":"📈 增长值不值","metric":"PEG","value":"0.66x","weight":"10%","rank":"#2/8","verdict":"<1, 增长远未定价"}
  ],
  "ranking_summary": "加权综合 = 3×40% + 1×25% + 1×25% + 2×10% = 2.05, 排名 #2/8",
  "composite_score": 2.05,
  "composite_rank_8": "#2/8",
  "layer_weights": {"L1":"40%","L2":"25%","L3":"25%","L4":"10%"},

  "f_score_items": [
    {"group":"盈利","criterion":"ROA > 0","score":1,"reason":"净利润$72.9B/总资产$116B=62.8%"},
    {"group":"盈利","criterion":"CFO > 0","score":1,"reason":"经营性现金流$74.3B"},
    {"group":"盈利","criterion":"ΔROA > 0","score":1,"reason":"ROA同比从48%升至62.8%"},
    {"group":"盈利","criterion":"CFO > NI","score":1,"reason":"CFO$74.3B > NI$72.9B"},
    {"group":"杠杆","criterion":"ΔLeverage < 0","score":1,"reason":"资产负债率下降"},
    {"group":"杠杆","criterion":"ΔLiquidity > 0","score":1,"reason":"流动比率上升"},
    {"group":"杠杆","criterion":"无增发","score":1,"reason":"今年无新股增发"},
    {"group":"效率","criterion":"ΔMargin > 0","score":1,"reason":"毛利率从72%升至75%"},
    {"group":"效率","criterion":"ΔTurnover > 0","score":0,"reason":"资产周转率略降"}
  ],
  "f_score_total": 8,

  "dashboard_metrics": [
    {"label":"营收增速","value":"+113%","note":"YoY"},
    {"label":"毛利率","value":"75.5%","note":"vs 行业53%"},
    {"label":"FCF利润率","value":"49%","note":"$35B"},
    {"label":"研发占比","value":"12.5%","note":"$16B"},
    {"label":"负债率","value":"15%","note":"净现金$32B"},
    {"label":"股息率","value":"0.02%","note":"不靠分红"},
    {"label":"机构持股","value":"68%","note":"高共识"},
    {"label":"Short Interest","value":"1.0%","note":"无轧空"},
    {"label":"Beta","value":"1.68","note":"高波动"},
    {"label":"PEG(Fwd)","value":"0.66x","note":"<1 划算"}
  ],

  "s5_body_html": "<p>估值分析描述</p>",
  "s5_valuation_methods": [
    {"name":"DCF保守","value":"$165","probability":"30%"},
    {"name":"DCF基准","value":"$245","probability":"50%"},
    {"name":"DCF乐观","value":"$310","probability":"20%"}
  ],

  "s6_body_html": "<p>未来展望</p>",
  "s6_scenarios": [
    {"scenario":"悲观","probability":"25%","price_target":"$140","return_pct":"-26.8%","description":"AI投资放缓，Blackwell需求低于预期"},
    {"scenario":"基准","probability":"50%","price_target":"$245","return_pct":"+27.9%","description":"AI capex持续增长，Blackwell正常量产"},
    {"scenario":"乐观","probability":"25%","price_target":"$310","return_pct":"+61.9%","description":"Blackwell Ultra超额需求，推理爆发"}
  ],

  "s7_risks": [
    {"risk":"AI投资周期见顶","probability":"中","impact":"营收增速放缓至30%以下","mitigation":"关注三大云厂商CapEx指引"},
    {"risk":"竞争加剧","probability":"中","impact":"ASIC/AMD蚕食市场份额","mitigation":"CUDA生态护城河极深"},
    {"risk":"地缘政治","probability":"高","impact":"出口管制限制中国营收","mitigation":"H20合规版保持稳定出货"},
    {"risk":"估值收缩","probability":"中","impact":"PE从45x压缩至30x=跌33%","mitigation":"增长率强劲支撑高PE"},
    {"risk":"客户自研芯片","probability":"低","impact":"Google/Amazon TPU长期替代","mitigation":"训练+推理全栈优势"}
  ],

  "s8_signal": {
    "signal":"BULLISH",
    "confidence":"HIGH",
    "horizon":"MEDIUM",
    "action":"BUY",
    "conviction":"STRONG",
    "rank_summary":"加权综合分 2.05, #2/8",
    "composite_rank":"#2/8"
  },

  "charts": [
    {"chart_id":"priceChart","chart_type":"line","section_id":"s3","labels":["25.03","25.05","25.07","25.09","25.11","26.01","26.03","26.05"],"datasets":[{"label":"NVDA","data":[145,152,140,160,170,175,165,191],"color":"#2563eb","fill":true,"tension":0.3,"point_radius":3}],"y_axis_label":"$","y_axis_format":"$"},
    {"chart_id":"valuationRadar","chart_type":"radar","section_id":"s5","labels":["DCF安全边际","P/E vs 行业","EV/EBITDA","PEG","ROIC vs WACC","利润率","FCF质量","护城河","F-Score","资产负债","盈利稳定性"],"datasets":[{"label":"NVDA","data":[65,40,35,85,95,90,95,95,90,85,90],"color":"#2563eb"}]},
    {"chart_id":"peerCompareChart","chart_type":"bar","section_id":"s5","labels":["NVDA","AMD","INTC","MU","行业均值"],"datasets":[{"label":"Forward PE","data":[45.3,38.2,-15.5,28.6,35.0],"point_background_colors":["#2563eb","#f97316","#8b5cf6","#10b981","#94a3b8"]}]},
    {"chart_id":"dcfChart","chart_type":"bar","section_id":"s5","labels":["当前价","悲观","基准","乐观"],"datasets":[{"label":"目标价","data":[191,165,245,310],"point_background_colors":["#d97706","#dc2626","#d97706","#059669"]}]},
    {"chart_id":"scenarioChart","chart_type":"bar","section_id":"s6","labels":["悲观(25%)","基准(50%)","乐观(25%)"],"datasets":[{"label":"预期回报%","data":[-26.8,27.9,61.9],"point_background_colors":["#dc2626","#d97706","#059669"]}],"y_axis_label":"%","y_axis_format":"%","tooltip_prefix":"","tooltip_suffix":"%"}
  ],

  "verdict": {
    "title":"最终裁决",
    "bull_points":[
      "ROIC 55%+ 碾压全市场，AI 芯片独占75%+训练市场",
      "Blackwell Ultra 2026H2 催化，营收+78% YoY",
      "PEG 0.66x < 1，增长尚未被定价",
      "F-Score 8/9，财务极健康",
      "CUDA生态锁定，转换成本极高"
    ],
    "bear_points":[
      "Forward PE 45x，估值高位依赖高增长持续",
      "出口管制升级风险(中国营收占比17%)",
      "客户自研芯片(Google TPU/AWS Trainium)长期替代",
      "AI Capex周期见顶若发生=估值+盈利双杀",
      "波动率Beta 1.68，不适合低风险偏好"
    ],
    "composite_rank":"#2/8",
    "f_score_total":"8/9",
    "recommendation":"强力推荐",
    "rec_class":"bull"
  },

  "sidebar_dots": {"s1":"bull","s3":"bull","s4":"bull","s5":"neut","s6":"bull","s7":"neut","s8":"bull"},
  "overrides": [],
  "footer_text": "InvestSkill v3.0 · 教育性分析，不构成投资建议"
}
"""


def run_search(report: StockReport, logger=None) -> StockReport:
    import time
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

## 四层加权排名体系 (深度价值导向)

所有8个投资标的一起排名: NVDA, AAPL, TSLA, INTC, AMD, MU, 小米(1810.HK), BTC。
排名范围 #1~8/8 (#1=最好, #8=最差)。

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
- 排名与其他7家统一对比

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
    log.info(f"  等待 LLM 响应 (Deepseek V4 Pro 通常 60-180s)...")

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
