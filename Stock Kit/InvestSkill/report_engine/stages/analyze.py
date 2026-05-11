"""Stage 2: 分析计算 — Greenblatt 排名 + F-Score + 图表"""
from langchain_openai import ChatOpenAI
from report_engine.config import get_deepseek_config
from report_engine.schema import StockReport

ANALYZE_SYSTEM_PROMPT = """你是投资分析 agent。计算 Greenblatt 排名、F-Score、生成图表。

规则:
1. 股票/港股: L1=EBIT/EV, L2=ROIC, L3=F-Score (综合排名=L1+L2)
2. 加密: L1=MVRV Z-Score, L2=算力+采用率, L3=改编F-Score
3. F-Score 逐项打分，每项写 reason
4. 图表: priceChart(line,S3) + valuationRadar(radar,S5) + peerCompareChart(bar,S5) + dcfChart(bar,S5) + scenarioChart(bar,S6)
5. 百分比用 +X% 或 -X%
6. 加密资产: 无PE则用MVRV替代，overrides中声明

输出: 完整 StockReport JSON
"""

def run_analyze(report: StockReport) -> StockReport:
    cfg = get_deepseek_config()
    llm = ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=0.1,
    )

    prompt = f"""分析 {report.company_name} ({report.ticker}), 类型: {report.asset_category.value}

当前数据:
```json
{report.model_dump_json(indent=2, exclude={'module_states'})}
```

完成所有分析字段:
1. greenblatt_ranking (L1/L2/L3)
2. f_score_items (9项逐条)
3. charts (5张: priceChart/valuationRadar/peerCompareChart/dcfChart/scenarioChart)
4. s5_body_html, s6_body_html, s3_body_html
5. s6_scenarios (3个情景)
6. s7_risks (5+项)
7. s8_signal
8. verdict
9. dashboard_metrics (10+指标)
10. sidebar_dots

加密资产: peerCompareChart/valuationRadar 改为 crypto_metrics 替代，在 overrides 声明。

返回完整 StockReport JSON。
"""
    try:
        response = llm.invoke(prompt + "\n\n只返回 JSON，不要 markdown 包裹。")
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        result = StockReport.model_validate_json(content)
        result.company_dir = report.company_dir
        print(f"[Stage 2] 分析完成，{len(result.charts)} 张图表，{len(result.f_score_items)} 项 F-Score")
        return result
    except Exception as e:
        print(f"[Stage 2] 失败: {e}")
        return report
