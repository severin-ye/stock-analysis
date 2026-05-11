"""快速测试 report_engine"""
import sys
sys.path.insert(0, '/home/severin/Codelib/股市分析/InvestSkill')

from report_engine.stages.scaffold import scaffold
from report_engine.stages.render import render
from report_engine.stages.validate import validate_schema
from report_engine.schema import ChartDef, ChartDataset, ChartType

def test_scaffold():
    report = scaffold('英伟达')
    assert report.ticker == 'NVDA'
    assert report.company_name == '英伟达'
    assert report.asset_category.value == 'stock'
    n_modules = len(report.module_states)
    missing = report.get_missing_required()
    print(f'  scaffold: {report.ticker} | 模块: {n_modules} | 缺失: {len(missing)}')
    assert n_modules > 15, f'Expected >15 modules, got {n_modules}'
    return report

def test_render(report):
    report.charts = [
        ChartDef(chart_id='priceChart', chart_type=ChartType.LINE, section_id='s3',
                 title='走势', labels=['1月', '2月'],
                 datasets=[ChartDataset(label='NVDA', data=[100, 110])]),
        ChartDef(chart_id='dcfChart', chart_type=ChartType.BAR, section_id='s5',
                 title='估值', labels=['保守', '基准', '乐观'],
                 datasets=[ChartDataset(label='DCF', data=[200, 300, 400],
                                        point_background_colors=['#dc2626', '#d97706', '#059669'])]),
        ChartDef(chart_id='scenarioChart', chart_type=ChartType.BAR, section_id='s6',
                 title='情景', labels=['悲观', '乐观'],
                 datasets=[ChartDataset(label='回报', data=[-10, 20])]),
    ]
    report.cover_kpi = []
    report.s1_price_changes = []
    report.s7_risks = []
    report.sidebar_dots = {'s1': 'bull', 's2': 'bull', 's3': 'bull', 's4': 'bull',
                           's5': 'bull', 's6': 'bull', 's7': 'bear', 's8': 'bull'}

    html = render(report)
    has_canvas = '<canvas' in html
    has_chart = 'new Chart(' in html
    has_section = 'id="s1"' in html
    print(f'  render: {len(html):,} chars | canvas={has_canvas} | chart.js={has_chart} | sections={has_section}')
    assert has_canvas
    assert has_chart
    assert has_section
    return html

def test_validate(report):
    issues = validate_schema(report)
    print(f'  validate: {len(issues)} issues')
    for i in issues:
        print(f'    {i}')

def test_btc():
    report = scaffold('比特币')
    assert report.ticker == 'BTC'
    assert report.asset_category.value == 'crypto'
    print(f'  BTC scaffold: {report.ticker} | 类别: {report.asset_category.value}')

if __name__ == '__main__':
    print('Stage 0: Scaffold')
    r = test_scaffold()
    print('\nStage 3: Render')
    html = test_render(r)
    print('\nStage 4: Validate')
    test_validate(r)
    print('\nBTC test')
    test_btc()
    print('\n✅ All tests passed')
