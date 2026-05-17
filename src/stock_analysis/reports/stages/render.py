"""Stage 3: Jinja2 模板渲染

职责: 将 StockReport JSON 渲染为完整 HTML。
纯 Python + Jinja2，不需要 LLM。
"""

import json
import logging
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from stock_analysis.reports.schema import ChartType, StockReport

TEMPLATE_DIR = Path(__file__).parent.parent / 'templates'


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=False)


def _css_alpha(color: str, alpha: float) -> str:
    if color.startswith('#'):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        return f'rgba({r},{g},{b},{alpha})'
    return color


def build_env():
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    env.filters['tojson'] = _json_dumps
    env.filters['css_alpha'] = _css_alpha
    return env


def render(report: StockReport) -> str:
    env = build_env()
    template = env.get_template('report.jinja2')

    for chart in report.charts:
        if chart.horizontal:
            chart.chart_type = ChartType.BAR

    section_labels = {
        's1': '涨跌比例总览',
        's2': report.s2.title if report.s2 else '公司概览',
        's3': '过去一年走势',
        's4': report.s4.title if report.s4 else '竞争格局',
        's5': '💰 估值分析',
        's6': '未来一年展望',
        's7': '风险矩阵',
        's8': '投资信号',
    }

    ctx = report.model_dump(mode='json')
    ctx['SECTION_LABELS'] = section_labels

    is_crypto = ctx.get('asset_category') in ('crypto',)
    is_pos = ctx.get('ticker') in ('ETH', 'SOL', 'BNB')
    ctx['is_crypto_asset'] = is_crypto
    ctx['is_pos_crypto'] = is_pos

    # 信号中文化
    signal_val_map = {
        'BULLISH': '看多', 'BEARISH': '看空', 'NEUTRAL': '中性',
        'HIGH': '高', 'MEDIUM': '中', 'LOW': '低',
        'SHORT': '短期', 'LONG-TERM': '长期',
        'BUY': '买入', 'HOLD': '持有', 'SELL': '卖出',
        'STRONG': '强', 'MODERATE': '中等', 'WEAK': '弱',
    }
    signal = ctx.get('s8_signal')
    if signal and isinstance(signal, dict):
        for key in ('signal', 'confidence', 'horizon', 'action', 'conviction'):
            if signal.get(key):
                signal[key] = signal_val_map.get(signal[key], signal[key])
        ctx['s8_signal'] = signal

    return template.render(**ctx)


def render_to_file(report: StockReport, output_path: str, logger: logging.Logger | None = None) -> str:
    if logger is None:
        logger = logging.getLogger('pipeline')

    t0 = time.time()

    ctx = report.model_dump(mode='json')
    serialized_size = len(json.dumps(ctx, ensure_ascii=False))
    logger.debug(f"  model_dump(mode='json') 大小: {serialized_size:,} bytes")

    charts_raw = ctx.get('charts', [])
    logger.debug(f"  图表数: {len(charts_raw)}")
    for c in charts_raw:
        ct = c.get('chart_type', 'unknown')
        cid = c.get('chart_id', '?')
        logger.debug(f"    {cid}: type={ct}, labels={len(c.get('labels',[]))}, datasets={len(c.get('datasets',[]))}")

    signal = ctx.get('s8_signal')
    if signal:
        logger.debug(f"  s8_signal: {signal}")
    else:
        logger.warning("  s8_signal: None (信号块将丢失)")

    html = render(report)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')

    elapsed = time.time() - t0
    file_size = path.stat().st_size

    logger.info(f"  渲染耗时: {elapsed:.1f}s, 文件大小: {file_size:,} bytes")

    canvas_count = html.count('<canvas')
    chart_js_count = html.count('new Chart(')
    html_entity_count = html.count('&#34;') + html.count('&#39;')
    logger.info(f"  图表: <canvas>={canvas_count}, new Chart()={chart_js_count}, HTML实体={html_entity_count}")

    if html_entity_count > 0 and html.find('<script>') != -1:
        script_start = html.find('<script>')
        if html_entity_count > 0:
            script_region = html[script_start:]
            entities_in_js = script_region.count('&#34;') + script_region.count('&#39;')
            logger.warning(f"  ⚠️  <script> 中存在 {entities_in_js} 处 HTML 实体！图表将失效！")

    return str(path)
