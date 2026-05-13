"""生成一份 mock NVDA 报告，验证模板输出"""
import sys, json
sys.path.insert(0, '/home/severin/Codelib/股市分析/InvestSkill')

from report_engine.stages.scaffold import scaffold
from report_engine.stages.render import render, render_to_file
from report_engine.schema import (
    StockReport, KPIItem, PriceChangeRow, CompanyOverview, KeyMetricRow,
    CompetitonSection, RankingRow, FScoreItem, ValuationMethod,
    ScenarioRow, RiskItem, SignalBlock, VerdictSection,
    ChartDef, ChartDataset, ChartType, SignalType, ConfidenceType,
    HorizonType, ActionType, ConvictionType
)

report = scaffold('英伟达')

# ── 填充数据 ──
report.cover_price = '$215.20'
report.cover_market_cap = '$3.2T'
report.cover_kpi = [
    KPIItem(label='52周变动', value='+98.8%', css_class='up'),
    KPIItem(label='YTD 2026', value='+15.3%', css_class='up'),
    KPIItem(label='远期 PE', value='25.8x'),
    KPIItem(label='PEG', value='0.66x', sub='↓ 低估'),
    KPIItem(label='ROIC', value='~50%+'),
    KPIItem(label='F-Score', value='8/9'),
]

report.s1_price_changes = [
    PriceChangeRow(dimension='YTD 2026', change_pct='+15.3%', corresponding_price='$186.50→$215.20', probability_weight='已实现', industry_compare='半导体均值 +8%'),
    PriceChangeRow(dimension='1年回报 (TTM)', change_pct='+98.8%', corresponding_price='~$101.5→$201.7', probability_weight='已实现', industry_compare='行业均值 +25%'),
    PriceChangeRow(dimension='分析师目标价', change_pct='+27.8%', corresponding_price='$215→$275', probability_weight='60%概率', industry_compare='—'),
    PriceChangeRow(dimension='DCF内在价值 (保守)', change_pct='+15~25%', corresponding_price='$215→$247~$269', probability_weight='50%概率', industry_compare='—'),
    PriceChangeRow(dimension='下行风险 (熊市)', change_pct='-20~-35%', corresponding_price='$215→$140~$172', probability_weight='25%概率', industry_compare='—'),
]
report.s1_core_judgment = '当前 Forward PE 25.8x，PEG 0.66，在 65.5% 营收增速支撑下估值合理偏低估。CUDA 生态护城河极宽。'

report.s2 = CompanyOverview(
    title='🏢 公司概览',
    subtitle='商业模式 · 核心竞争力',
    body_html='<p>英伟达 (NVIDIA, NASDAQ: NVDA) 是全球 AI 计算芯片龙头。</p>',
    key_metrics=[
        KeyMetricRow(label='市值', value='$3.2T'),
        KeyMetricRow(label='营收增速 (YoY)', value='+65.5%'),
        KeyMetricRow(label='毛利率', value='75.0%'),
    ],
)

report.s3_body_html = '<p>过去一年 NVDA 股价从 ~$101 涨至 $215，涨幅近 100%。AI 算力需求驱动下，数据中心营收占比超 90%。</p>'

report.s4 = CompetitonSection(
    title='⚔️ 竞争格局',
    subtitle='Porter\'s Five Forces · 护城河评级',
    body_html='<p>CUDA 生态锁定效应极强，但面临客户自研芯片（Google TPU、AWS Trainium）的长期威胁。</p>',
)

report.greenblatt_ranking = [
    RankingRow(layer='L1', dimension='💰 便不便宜', metric='EBIT/EV', value='2.52%', rank='#3/6', verdict='偏低但非极端折扣'),
    RankingRow(layer='L2', dimension='🏭 赚不赚钱', metric='ROIC', value='50%+', rank='#1/6', verdict='全球最赚钱半导体企业'),
    RankingRow(layer='L3', dimension='🛡️ 会不会崩', metric='F-Score', value='8/9', rank='—', verdict='财务极其健康'),
]
report.greenblatt_summary = 'Greenblatt: EBIT/EV 2.52% · ROIC 50%+ · F-Score 8/9 → 强力推荐'
report.f_score_total = "8"
report.f_score_items = [
    FScoreItem(group='盈利', criterion='ROA > 0', score=1, reason='TTM 净利润率 55.6%'),
    FScoreItem(group='盈利', criterion='CFO > 0', score=1, reason='FCF 利润率 44.8%'),
    FScoreItem(group='盈利', criterion='ΔROA', score=1, reason='利润率持续扩张'),
    FScoreItem(group='盈利', criterion='CFO > NI', score=1, reason='FCF/NI 比 83%'),
    FScoreItem(group='杠杆', criterion='ΔLeverage', score=1, reason='零负债，净现金状态'),
    FScoreItem(group='杠杆', criterion='ΔLiquidity', score=1, reason='流动比率极强'),
    FScoreItem(group='杠杆', criterion='No Equity Offer', score=1, reason='$58.5B 回购'),
    FScoreItem(group='效率', criterion='ΔMargin', score=1, reason='毛利率 72%→75%'),
    FScoreItem(group='效率', criterion='ΔTurnover', score=0, reason='资产周转率增速可能放缓'),
]

report.dashboard_metrics = [
    KeyMetricRow(label='营收增长率', value='+65.5%', note='YoY'),
    KeyMetricRow(label='毛利率', value='75.0%'),
    KeyMetricRow(label='营业利润率', value='60.4%'),
    KeyMetricRow(label='净利润率', value='55.6%'),
    KeyMetricRow(label='PE (FWD)', value='25.80x'),
    KeyMetricRow(label='PEG', value='0.66x'),
    KeyMetricRow(label='ROIC', value='~50%+'),
    KeyMetricRow(label='FCF 收益率', value='1.85%'),
    KeyMetricRow(label='F-Score', value='8-9/9'),
    KeyMetricRow(label='分析师目标价', value='$275 (+28%)'),
]

report.s5_body_html = '<p>多维估值显示 NVDA 在当前价格仍具吸引力。</p>'
report.s5_valuation_methods = [
    ValuationMethod(name='DCF 保守', value='$247', probability='50%'),
    ValuationMethod(name='DCF 基准', value='$269', probability='35%'),
    ValuationMethod(name='DCF 乐观', value='$380', probability='15%'),
]

report.s6_body_html = '<p>未来一年 AI 推理需求从训练转向部署，打开第二轮增长空间。</p>'
report.s6_scenarios = [
    ScenarioRow(scenario='悲观', probability='25%', price_target='$140', return_pct='-35%', description='AI 资本开支收缩'),
    ScenarioRow(scenario='基准', probability='45%', price_target='$275', return_pct='+28%', description='营收增长 30%'),
    ScenarioRow(scenario='乐观', probability='30%', price_target='$380', return_pct='+77%', description='推理需求井喷'),
]

report.s7_risks = [
    RiskItem(risk='客户自研芯片替代', probability='中 (30%)', impact='高', mitigation='CUDA 生态锁定效应'),
    RiskItem(risk='地缘政治出口管制', probability='中 (25%)', impact='高', mitigation='中国特供版芯片'),
    RiskItem(risk='AI 泡沫破裂', probability='低 (15%)', impact='极高', mitigation='实际应用落地验证'),
    RiskItem(risk='竞争加剧', probability='中 (20%)', impact='中', mitigation='技术领先 2-3 年'),
    RiskItem(risk='毛利率压缩', probability='低 (10%)', impact='中', mitigation='定价权极强'),
]

report.s8_signal = SignalBlock(
    signal=SignalType.BULLISH, confidence=ConfidenceType.HIGH,
    horizon=HorizonType.MEDIUM, action=ActionType.BUY,
    conviction=ConvictionType.STRONG,
    rank_summary='L1#3 + L2#1 = 4 → #2/6',
    composite_rank='#2/6'
)

report.verdict = VerdictSection(
    bull_points=[
        'CUDA 生态护城河全球最宽',
        'AI 数据中心需求持续爆发',
        '65.5% 营收增速支撑当前估值',
        'ROIC 50%+ 碾压级盈利能力',
        'F-Score 8/9 财务极其健康',
    ],
    bear_points=[
        '客户自研芯片长期替代威胁',
        '地缘政治出口管制风险',
        '估值不低 (PE 25.8x)',
        'AI 泡沫破裂尾部风险',
        '营收增速能否持续存疑',
    ],
    composite_rank='L1#3 + L2#1 = 4 → #2/6',
    f_score_total='8/9',
    recommendation='强力推荐',
    rec_class='bull',
)

report.charts = [
    ChartDef(chart_id='priceChart', chart_type=ChartType.LINE, section_id='s3',
             title='NVDA 股价走势', y_axis_label='$', y_axis_format='$',
             labels=['5月','6月','7月','8月','9月','10月','11月','12月','1月','2月','3月','4月','5月'],
             datasets=[ChartDataset(label='NVDA 股价', color='#2563eb',
                                    data=[101,115,132,148,165,180,188,192,186,195,199,213,215])]),
    ChartDef(chart_id='valuationRadar', chart_type=ChartType.RADAR, section_id='s5',
             title='VM 评分雷达', y_axis_label='%', y_axis_format='%',
             labels=['DCF安全边际','P/E vs 行业','EV/EBITDA','PEG','ROIC vs WACC','利润率','FCF质量','护城河','F-Score','资产负债','盈利稳定性'],
             datasets=[ChartDataset(label='NVDA', color='#2563eb',
                                    data=[67,80,38,86,100,100,75,100,100,80,80])]),
    ChartDef(chart_id='peerCompareChart', chart_type=ChartType.BAR, section_id='s5',
             title='Forward PE 对比', y_axis_label='x', y_axis_format='x',
             labels=['NVDA','AMD','AVGO','QCOM','行业均值'],
             datasets=[ChartDataset(label='Forward PE',
                                    data=[25.8,40,30,20,25],
                                    point_background_colors=['#2563eb','#f97316','#8b5cf6','#10b981','#94a3b8'])]),
    ChartDef(chart_id='dcfChart', chart_type=ChartType.BAR, section_id='s5',
             title='DCF 估值情景', y_axis_label='$', y_axis_format='$',
             labels=['保守','基准','乐观'],
             datasets=[ChartDataset(label='目标价',
                                    data=[247,269,380],
                                    point_background_colors=['#dc2626','#d97706','#059669'])]),
    ChartDef(chart_id='scenarioChart', chart_type=ChartType.BAR, section_id='s6',
             title='情景分析', y_axis_label='%', y_axis_format='%', tooltip_prefix='', tooltip_suffix='%',
             labels=['悲观 (25%)','基准 (45%)','乐观 (30%)'],
             datasets=[ChartDataset(label='预期回报',
                                    data=[-27,27,40],
                                    point_background_colors=['#dc2626','#d97706','#059669'])]),
]

report.sidebar_dots = {f's{i}': 'bull' if i != 7 else 'bear' for i in range(1,9)}

# ── 渲染 ──
html = render(report)
output_path = '/home/severin/Codelib/股市分析/英伟达/260511_测试报告.html'
render_to_file(report, output_path)

sections_ok = all(f'id="s{i}"' in html for i in range(1, 9))
verdict_ok = 'id="verdict"' in html
body_ok = '</body>' in html
print(f'✅ 渲染完成: {output_path}')
print(f'   大小: {len(html):,} chars')
print(f'   Sections: {"✅" if sections_ok else "❌"}')
print(f'   Charts: {html.count("new Chart(")} 个')
print(f'   Canvas: {html.count("<canvas")} 个')
print(f'   Verdict: {"✅" if verdict_ok else "❌"}')
print(f'   Body闭合: {"✅" if body_ok else "❌"}')
