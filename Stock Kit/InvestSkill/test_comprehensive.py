"""
综合测试: HTML 报告完整性 + Schema 验证 + 渲染正确性

验证所有 8 家 260511 报告的质量，不依赖 LLM。
"""
import pytest
import json
import os
import re
from pathlib import Path
from report_engine.schema import StockReport

BASE = Path('/home/severin/Codelib/股市分析')
REPORT_DIRS = ['英伟达', '苹果', '特斯拉', '英特尔', 'AMD', '美光', '小米', '比特币']
REPORT_DATE = '260511'


# ═══════════════════════════════════════
# 1. 文件存在性
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_report_exists(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    assert path.exists(), f'{company} 报告不存在: {path}'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_report_size(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert len(html) > 20000, f'{company} 报告小于 20KB ({len(html):,} bytes)'


# ═══════════════════════════════════════
# 2. HTML 结构完整性
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_html_structure(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert '<!DOCTYPE html>' in html
    assert '</html>' in html
    assert '</body>' in html


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_eight_sections(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    for sid in ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']:
        assert f'id="{sid}"' in html, f'{company} 缺少 section {sid}'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_verdict_exists(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert 'id="verdict"' in html, f'{company} 缺少 Verdict'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_sidebar_exists(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert 'class="sidebar"' in html, f'{company} 缺少 sidebar'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_cover_has_kpi(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert 'kpi-strip' in html, f'{company} 封面缺少 KPI strip'


# ═══════════════════════════════════════
# 3. S3 走势图验证
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_s3_has_chart(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    s3_start = html.find('id="s3"')
    s4_start = html.find('id="s4"')
    s3_html = html[s3_start:s4_start] if s4_start > s3_start else html[s3_start:]
    assert '<canvas' in s3_html, f'{company} S3 缺少图表'



@pytest.mark.parametrize('company', REPORT_DIRS)
def test_s3_has_chart_js(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert "new Chart(document.getElementById('priceChart')" in html or \
           'new Chart(document.getElementById("priceChart")' in html, \
        f'{company} S3 priceChart 缺少 JS 初始化'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_s3_has_text(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    s3_start = html.find('id="s3"')
    s4_start = html.find('id="s4"')
    s3_html = html[s3_start:s4_start]
    text = re.sub(r'<[^>]+>', ' ', s3_html).strip()
    text = re.sub(r'\s+', ' ', text)
    assert len(text) > 80, f'{company} S3 文字内容过短 ({len(text)} 字)'


# ═══════════════════════════════════════
# 4. S5 排名表验证 (四层)
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_four_layer_ranking(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    for layer in ['L1', 'L2', 'L3', 'L4']:
        assert f'<strong>{layer}</strong>' in html, \
            f'{company} 排名表缺少 {layer}'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_ranking_has_weights(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    for weight in ['40%', '25%', '10%']:
        assert weight in html, f'{company} 排名表缺少权重 {weight}'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_ranking_has_composite(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    assert '加权综合' in html, f'{company} 排名表缺少综合排名行'
    assert '综合排名' in html or 'composite' in html.lower(), f'{company} 缺少综合排名显示'


# ═══════════════════════════════════════
# 5. F-Score 验证
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_f_score_nine_items(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    fscore_section = re.search(
        r'Piotroski F-Score.*?</table>', html, re.DOTALL)
    assert fscore_section, f'{company} 缺少 F-Score 表格'
    rows = re.findall(r'<tr[^>]*>', fscore_section.group(0))
    assert len(rows) >= 10, f'{company} F-Score 行数 {len(rows)} (期望 >= 10)'


# ═══════════════════════════════════════
# 6. 投资信号块验证
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_signal_not_empty(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    # Signal, Confidence, Horizon, Action, Conviction 都应有非空值
    signal_section = html[html.find('INVESTMENT SIGNAL'):html.find('INVESTMENT SIGNAL') + 1500]
    for field in ['Signal', 'Confidence', 'Horizon', 'Action', 'Conviction']:
        idx = signal_section.find(f'{field}</label>')
        if idx == -1:
            continue
        span_start = signal_section.find('<span', idx)
        span_end = signal_section.find('</span>', span_start)
        span_content = signal_section[span_start:span_end]
        inner = re.sub(r'<[^>]+>', '', span_content).strip()
        assert len(inner) > 0, f'{company} S8 {field} 为空'


# ═══════════════════════════════════════
# 7. Verdict 验证
# ═══════════════════════════════════════

@pytest.mark.parametrize('company', REPORT_DIRS)
def test_verdict_has_bull_bear(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    verdict_idx = html.find('id="verdict"')
    verdict_html = html[verdict_idx:verdict_idx + 3000]
    assert '看多理由' in verdict_html, f'{company} Verdict 缺少看多理由'
    assert '看空理由' in verdict_html, f'{company} Verdict 缺少看空理由'
    bull_items = len(re.findall(r'<li>', html[verdict_idx:html.find('看空理由', verdict_idx)]))
    assert bull_items >= 3, f'{company} 看多理由少于3条 ({bull_items})'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_verdict_has_recommendation(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    verdict_idx = html.find('id="verdict"')
    verdict_html = html[verdict_idx:verdict_idx + 4000]
    assert 'rec"' in verdict_html or 'rec ' in verdict_html, \
        f'{company} Verdict 缺少推荐标签'


# ═══════════════════════════════════════
# 8. 所有图表验证
# ═══════════════════════════════════════

REQUIRED_CHARTS = ['priceChart', 'valuationRadar', 'peerCompareChart', 'dcfChart', 'scenarioChart']


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_all_charts_exist(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    for cid in REQUIRED_CHARTS:
        assert f'id="{cid}"' in html, f'{company} 缺少图表 {cid}'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_all_charts_have_js(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    for cid in REQUIRED_CHARTS:
        assert f"new Chart(document.getElementById('{cid}')" in html or \
               f'new Chart(document.getElementById("{cid}")' in html, \
            f'{company} 图表 {cid} 缺少 JS 初始化代码'


@pytest.mark.parametrize('company', REPORT_DIRS)
def test_chart_count_matches(company):
    path = BASE / company / f'{REPORT_DATE}_综合分析报告.html'
    html = path.read_text(encoding='utf-8')
    canvases = len(re.findall(r'<canvas', html))
    chart_js = len(re.findall(r'new Chart\(', html))
    assert canvases == chart_js, \
        f'{company} canvas 数 ({canvases}) ≠ Chart.js 数 ({chart_js})'


# ═══════════════════════════════════════
# 9. Schema 验证 (用 mock 数据)
# ═══════════════════════════════════════

def test_schema_ranking_row():
    """验证 RankingRow 包含 4 层所有字段"""
    from report_engine.schema import RankingRow
    row = RankingRow(layer='L4', dimension='📈 增长值不值', metric='PEG',
                     value='0.66x', weight='10%', rank='#2/8',
                     verdict='<1, 划算')
    d = row.model_dump()
    assert d['layer'] == 'L4'
    assert d['weight'] == '10%'
    assert d['rank'] == '#2/8'


def test_schema_composite_fields():
    """验证 StockReport 包含 composite_score 和 composite_rank_8"""
    from report_engine.schema import StockReport
    r = StockReport(composite_score=1.85, composite_rank_8='#2/8',
                    ticker='TEST', company_name='测试', company_name_en='Test',
                    report_date='2026-05-11', data_date='测试')
    assert r.composite_score == 1.85
    assert r.composite_rank_8 == '#2/8'


def test_schema_layer_weights():
    """验证默认权重"""
    from report_engine.schema import StockReport
    r = StockReport(composite_score=0, composite_rank_8='', ticker='T', company_name='T',
                    company_name_en='T', report_date='', data_date='')
    assert r.layer_weights == {'L1': '40%', 'L2': '25%', 'L3': '25%', 'L4': '10%'}


def test_schema_fscore_validation():
    """F-Score items 必须有 9 条，每条的 score 是 0 或 1"""
    from report_engine.schema import FScoreItem, StockReport
    
    items = [
        FScoreItem(group='盈利', criterion='ROA > 0', score=1, reason='...'),
        FScoreItem(group='盈利', criterion='CFO > 0', score=1, reason='...'),
        FScoreItem(group='盈利', criterion='delta ROA > 0', score=1, reason='...'),
        FScoreItem(group='盈利', criterion='CFO > NI', score=1, reason='...'),
        FScoreItem(group='杠杆', criterion='delta Leverage < 0', score=1, reason='...'),
        FScoreItem(group='杠杆', criterion='delta Liquidity > 0', score=0, reason='...'),
        FScoreItem(group='杠杆', criterion='No Equity Offer', score=1, reason='...'),
        FScoreItem(group='效率', criterion='delta Margin > 0', score=1, reason='...'),
        FScoreItem(group='效率', criterion='delta Turnover > 0', score=0, reason='...'),
    ]
    assert len(items) == 9
    for item in items:
        assert item.score in (0, 1)
    total = sum(i.score for i in items)
    assert 0 <= total <= 9


def test_schema_charts_required():
    """验证图表 ID 不重复"""
    from report_engine.schema import ChartDef, ChartType
    charts = [
        ChartDef(chart_id='priceChart', chart_type=ChartType.LINE, section_id='s3',
                 labels=['a', 'b'], datasets=[]),
        ChartDef(chart_id='valuationRadar', chart_type=ChartType.RADAR, section_id='s5',
                 labels=['a', 'b'], datasets=[]),
        ChartDef(chart_id='peerCompareChart', chart_type=ChartType.BAR, section_id='s5',
                 labels=['a', 'b'], datasets=[]),
        ChartDef(chart_id='dcfChart', chart_type=ChartType.BAR, section_id='s5',
                 labels=['a', 'b'], datasets=[]),
        ChartDef(chart_id='scenarioChart', chart_type=ChartType.BAR, section_id='s6',
                 labels=['a', 'b'], datasets=[]),
    ]
    ids = [c.chart_id for c in charts]
    assert len(ids) == len(set(ids)), f'图表 ID 重复: {ids}'


# ═══════════════════════════════════════
# 10. 枚举序列化测试 (根因测试)
# ═══════════════════════════════════════

def test_model_dump_json_converts_enums_to_strings():
    from report_engine.schema import (
        StockReport, ChartDef, ChartType, SignalBlock,
    )

    report = StockReport(
        composite_score=0, composite_rank_8='',
        ticker='TEST', company_name='测试', company_name_en='Test',
        report_date='', data_date='', asset_category='stock',
    )
    report.charts = [
        ChartDef(chart_id='c1', chart_type=ChartType.LINE, section_id='s3',
                 labels=['a'], datasets=[]),
        ChartDef(chart_id='c2', chart_type=ChartType.BAR, section_id='s5',
                 labels=['a'], datasets=[]),
        ChartDef(chart_id='c3', chart_type=ChartType.RADAR, section_id='s5',
                 labels=['a'], datasets=[]),
    ]
    report.s8_signal = SignalBlock(
        signal='BULLISH', confidence='HIGH', horizon='MEDIUM',
        action='BUY', conviction='STRONG',
    )

    d = report.model_dump(mode='json')

    assert d['charts'][0]['chart_type'] == 'line', \
        f"Expected 'line', got {d['charts'][0]['chart_type']}"
    assert d['charts'][1]['chart_type'] == 'bar'
    assert d['charts'][2]['chart_type'] == 'radar'

    assert isinstance(d['s8_signal']['signal'], str)
    assert d['s8_signal']['signal'] == 'BULLISH'
    assert d['s8_signal']['confidence'] == 'HIGH'

    assert d['asset_category'] == 'stock'


def test_model_dump_python_mode_keeps_enums():
    from report_engine.schema import ChartDef, ChartType
    chart = ChartDef(chart_id='c', chart_type=ChartType.LINE, section_id='s3',
                     labels=[], datasets=[])
    d = chart.model_dump()
    assert type(d['chart_type']) is ChartType
    d2 = chart.model_dump(mode='json')
    assert type(d2['chart_type']) is str


def test_chart_type_enum_values():
    from report_engine.schema import ChartType
    assert ChartType.LINE == 'line'
    assert ChartType.BAR == 'bar'
    assert ChartType.RADAR == 'radar'


def test_signal_enum_values():
    from report_engine.schema import (
        SignalType, ConfidenceType, HorizonType,
        ActionType, ConvictionType,
    )
    assert SignalType.BULLISH == 'BULLISH'
    assert SignalType.NEUTRAL == 'NEUTRAL'
    assert SignalType.BEARISH == 'BEARISH'
    assert ConfidenceType.HIGH == 'HIGH'
    assert HorizonType.MEDIUM == 'MEDIUM'
    assert ActionType.BUY == 'BUY'
    assert ConvictionType.STRONG == 'STRONG'


# ═══════════════════════════════════════
# 11. 集成: Mock report → HTML 渲染
# ═══════════════════════════════════════

def test_render_integration(tmp_path):
    """用 mock 数据渲染 HTML 并验证关键元素"""
    from report_engine.schema import (
        StockReport, KPIItem, PriceChangeRow, CompanyOverview,
        KeyMetricRow, CompetitonSection, RankingRow, FScoreItem,
        ValuationMethod, ScenarioRow, RiskItem, SignalBlock,
        VerdictSection, ChartDef, ChartType, ChartDataset,
    )
    from report_engine.stages.render import render

    report = StockReport(
        ticker='TEST', company_name='测试公司', company_name_en='Test Corp',
        exchange='NASDAQ', sector='科技', report_date='2026-05-11',
        data_date='2026-05-10 收盘',
        cover_title='TEST — 测试公司 综合投资分析',
        cover_price='$100.00', cover_market_cap='$1万亿',
        cover_kpi=[
            KPIItem(label='当前股价', value='$100.00', css_class='up'),
            KPIItem(label='YTD', value='+20%', css_class='up'),
        ],
        s1_price_changes=[
            PriceChangeRow(dimension='1日', change_pct='+1.5%',
                          corresponding_price='$98.5→$100',
                          probability_weight='—', industry_compare='板块+0.8%'),
        ],
        s1_core_judgment='这是一家好公司',
        s2=CompanyOverview(title='🏢 公司概览', subtitle='科技公司',
                          body_html='<p>测试公司描述</p>',
                          key_metrics=[KeyMetricRow(label='市值', value='$1万亿')]),
        s3_body_html='<p>过去一年走势描述文本，详细说明价格走势和催化剂。</p>',
        s4=CompetitonSection(title='⚔️ 竞争格局', subtitle='行业竞争',
                            body_html='<p>竞争分析内容</p>'),
        greenblatt_ranking=[
            RankingRow(layer='L1', dimension='💰 便不便宜', metric='EBIT/EV',
                      value='5.0%', weight='40%', rank='#1/8', verdict='便宜'),
            RankingRow(layer='L2', dimension='🏭 赚不赚钱', metric='ROIC',
                      value='30%', weight='25%', rank='#2/8', verdict='优秀'),
            RankingRow(layer='L3', dimension='🛡️ 会不会崩', metric='F-Score',
                      value='8/9', weight='25%', rank='#1/8', verdict='极其健康'),
            RankingRow(layer='L4', dimension='📈 增长值不值', metric='PEG',
                      value='0.8x', weight='10%', rank='#3/8', verdict='划算'),
        ],
        ranking_summary='加权综合 = 1×40% + 2×25% + 1×25% + 3×10% = 1.55',
        composite_score=1.55,
        composite_rank_8='#1/8',
        f_score_items=[
            FScoreItem(group='盈利', criterion='ROA > 0', score=1, reason='ROA 15%'),
            FScoreItem(group='盈利', criterion='CFO > 0', score=1, reason='CFO +'),
            FScoreItem(group='盈利', criterion='ΔROA > 0', score=1, reason='ROA 上升'),
            FScoreItem(group='盈利', criterion='CFO > NI', score=1, reason='CFO > NI'),
            FScoreItem(group='杠杆', criterion='ΔLeverage < 0', score=1, reason='负债降'),
            FScoreItem(group='杠杆', criterion='ΔLiquidity > 0', score=1, reason='流动升'),
            FScoreItem(group='杠杆', criterion='无增发', score=1, reason='无增发'),
            FScoreItem(group='效率', criterion='ΔMargin > 0', score=1, reason='毛利率升'),
            FScoreItem(group='效率', criterion='ΔTurnover > 0', score=0, reason='周转率降'),
        ],
        f_score_total=8,
        s5_body_html='<p>估值分析内容</p>',
        s5_valuation_methods=[
            ValuationMethod(name='DCF基准', value='$120', probability='50%'),
        ],
        dashboard_metrics=[KeyMetricRow(label='营收增速', value='+15%', note='YoY')],
        s6_body_html='<p>未来展望内容</p>',
        s6_scenarios=[
            ScenarioRow(scenario='基准', probability='50%', price_target='$120',
                       return_pct='+20%', description='正常增长'),
        ],
        s7_risks=[
            RiskItem(risk='竞争加剧', probability='中', impact='份额下降',
                    mitigation='加大研发'),
        ],
        s8_signal=SignalBlock(signal='BULLISH', confidence='HIGH', horizon='MEDIUM',
                             action='BUY', conviction='STRONG',
                             rank_summary='综合分 1.55', composite_rank='#1/8'),
        charts=[
            ChartDef(chart_id='priceChart', chart_type=ChartType.LINE, section_id='s3',
                     labels=['Jan', 'Feb', 'Mar'],
                     datasets=[ChartDataset(label='TEST', data=[90, 95, 100],
                                            color='#2563eb', fill=True)]),
            ChartDef(chart_id='valuationRadar', chart_type=ChartType.RADAR, section_id='s5',
                     labels=['A', 'B', 'C'],
                     datasets=[ChartDataset(label='TEST', data=[50, 60, 70],
                                            color='#2563eb')]),
            ChartDef(chart_id='peerCompareChart', chart_type=ChartType.BAR, section_id='s5',
                     labels=['A', 'B'],
                     datasets=[ChartDataset(label='TEST', data=[10, 20],
                                            point_background_colors=['#2563eb', '#f97316'])]),
            ChartDef(chart_id='dcfChart', chart_type=ChartType.BAR, section_id='s5',
                     labels=['当前', '目标'],
                     datasets=[ChartDataset(label='TEST', data=[100, 120],
                                            point_background_colors=['#d97706', '#059669'])]),
            ChartDef(chart_id='scenarioChart', chart_type=ChartType.BAR, section_id='s6',
                     labels=['悲观', '基准', '乐观'],
                     datasets=[ChartDataset(label='TEST', data=[-10, 20, 50],
                                            point_background_colors=['#dc2626', '#d97706', '#059669'])]),
        ],
        verdict=VerdictSection(
            title='最终裁决',
            bull_points=['利润率高', '护城河深', '估值合理', '管理层优秀', '行业顺风'],
            bear_points=['竞争激烈', '监管风险', '周期性强', '估值高位', '宏观不确定性'],
            composite_rank='#1/8', f_score_total='8/9',
            recommendation='强力推荐', rec_class='bull',
        ),
        sidebar_dots={'s1': 'bull', 's2': 'bull', 's3': 'bull', 's4': 'neut',
                      's5': 'bull', 's6': 'bull', 's7': 'neut', 's8': 'bull'},
        footer_text='InvestSkill v3.0 · 教育性分析，不构成投资建议',
    )

    html = render(report)

    # 验证
    assert '<!DOCTYPE html>' in html

    # 8 个 section
    for sid in ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']:
        assert f'id="{sid}"' in html, f'缺少 {sid}'

    # 四层排名
    for layer in ['L1', 'L2', 'L3', 'L4']:
        assert f'<strong>{layer}</strong>' in html, f'缺少排名 {layer}'

    # 综合排名
    assert '加权综合' in html
    assert '#1/8' in html

    # F-Score
    assert 'Piotroski F-Score' in html
    assert '8/9' in html

    # 5 张图表都有 canvas + JS
    for cid in REQUIRED_CHARTS:
        assert f'id="{cid}"' in html, f'缺少 canvas {cid}'
        assert f"new Chart(document.getElementById('{cid}')" in html or \
               f'new Chart(document.getElementById("{cid}")' in html, \
            f'缺少 JS 初始化 {cid}'

    # 信号块非空
    assert 'BULLISH' in html
    assert 'HIGH' in html
    assert 'BUY' in html
    assert 'STRONG' in html

    # Verdict
    assert '看多理由' in html
    assert '看空理由' in html
    assert '强力推荐' in html

    # 投资信号
    assert 'INVESTMENT SIGNAL' in html

    # Canvas 数 = Chart.js 数
    canvases = len(re.findall(r'<canvas', html))
    charts_js = len(re.findall(r'new Chart\(', html))
    assert canvases == charts_js, f'canvas={canvases} chart_js={charts_js}'
    assert canvases == 5, f'应该有 5 张图表，实际 {canvases}'
