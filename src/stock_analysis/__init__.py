"""
stock_kit Tools — 数据采集 + 排名计算 + 报告渲染

与 InvestSkill 的分工:
  · InvestSkill = 方法论 (prompt 框架, 评分体系, HTML 模板)
  · Tools = 实现 (数据抓取, 纯数学排名, 渲染, 验证)

联动方式:
  · fetcher 按 InvestSkill 指定的数据源抓取
  · ranker 实现 InvestSkill 定义的四层加权公式
  · renderer 使用 InvestSkill 的 Jinja2 模板
"""
