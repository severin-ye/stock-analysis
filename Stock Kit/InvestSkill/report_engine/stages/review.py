"""Stage 2.5: 审核 Agent — 最多2轮协商"""
from langchain_openai import ChatOpenAI
from report_engine.config import get_deepseek_config
from report_engine.schema import StockReport, ModuleStatus, NegotiationResult
import json

REVIEW_PROMPT = """你是投资报告审核 agent。审核模块豁免是否合理。

规则:
- stock/hk_stock: 必须 PE、EBIT/EV、ROIC。豁免 PE = 不合理，驳回
- crypto: PE不适用，用MVRV替代 = 合理，批准
- 可选模块(required=False)找不到 = warning approve
- 驳回必须给 fix_suggestion (去哪搜)

输出 NegotiationResult JSON。
"""

def run_review(report: StockReport) -> StockReport:
    cfg = get_deepseek_config()
    llm = ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=0.0,
    )

    prev_round = report.negotiation_result.round if report.negotiation_result else 0
    prev_rejections = (
        [r for r in report.negotiation_result.module_results if not r.approved]
        if report.negotiation_result else []
    )

    prompt = f"""审核 {report.company_name} ({report.ticker}), 类型: {report.asset_category.value}
轮次: {prev_round + 1}

豁免申请:
```json
{json.dumps([o.model_dump() for o in report.overrides], indent=2, ensure_ascii=False)}
```

缺失模块: {report.get_missing_required()}
上一轮驳回: {json.dumps([r.model_dump() for r in prev_rejections], indent=2, ensure_ascii=False) if prev_rejections else '无'}

返回 NegotiationResult。
"""
    try:
        response = llm.invoke(prompt + "\n\n只返回 JSON。")
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        result = NegotiationResult.model_validate_json(content)
        report.negotiation_result = result

        for mr in result.module_results:
            mod_state = report.module_states.get(mr.module_id)
            if mod_state:
                mod_state.review_result = mr
                mod_state.status = ModuleStatus.EXEMPTED if mr.approved else ModuleStatus.REJECTED
        print(f"[Stage 2.5] 审核: {result.verdict}")
    except Exception as e:
        print(f"[Stage 2.5] 失败: {e}")

    return report
