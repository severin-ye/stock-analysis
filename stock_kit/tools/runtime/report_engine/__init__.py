"""InvestSkill Report Engine v2.0

JSON 驱动的投资分析报告生成引擎。
5 阶段 LangGraph 流水线，Jinja2 模板渲染。
"""

from tools.runtime.report_engine.pipeline import run