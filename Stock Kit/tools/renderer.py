"""Jinja2 渲染器 — 使用 InvestSkill 的模板生成 HTML

从 Stock Kit/InvestSkill/_template.html 加载 CSS 基础样式,
从 Stock Kit/InvestSkill/templates/report.jinja2 加载报告模板。
"""

import json
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

INVESTSKILL_DIR = Path(__file__).parent.parent / 'InvestSkill'
TEMPLATE_DIR = INVESTSKILL_DIR / 'templates'


def _json_dumps(value):
    return json.dumps(value, ensure_ascii=False)


def _css_alpha(color: str, alpha: float) -> str:
    if color.startswith('#'):
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
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


def render_html(report_data: dict, logger: logging.Logger | None = None) -> str:
    """将 report_data (model_dump JSON dict) 渲染为 HTML 字符串"""
    log = logger or logging.getLogger('tools.renderer')
    env = build_env()
    template = env.get_template('report.jinja2')

    charts = report_data.get('charts', [])
    for chart in charts:
        if chart.get('horizontal'):
            chart['chart_type'] = 'bar'

    section_labels = {
        's1': '涨跌比例总览',
        's2': report_data.get('s2', {}).get('title', '公司概览'),
        's3': '过去一年走势',
        's4': report_data.get('s4', {}).get('title', '竞争格局'),
        's5': '估值分析',
        's6': '未来一年展望',
        's7': '风险矩阵',
        's8': '投资信号',
    }
    report_data['SECTION_LABELS'] = section_labels

    html = template.render(**report_data)

    canvas_count = html.count('<canvas')
    chart_js_count = html.count('new Chart(')
    entities = html.count('&#34;') + html.count('&#39;')
    log.info(f"渲染完成: canvas={canvas_count}, charts={chart_js_count}, entities={entities}")

    if entities > 0:
        log.warning(f"⚠️ HTML 实体在 script 中: {entities} 处! 图表可能不渲染!")

    return html


def write_html(report_data: dict, output_path: str, logger: logging.Logger | None = None) -> str:
    """渲染并写入文件, 返回文件路径"""
    log = logger or logging.getLogger('tools.renderer')

    html = render_html(report_data, logger=log)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')
    log.info(f"写入: {path} ({path.stat().st_size:,} bytes)")
    return str(path)
