"""Stage 4: 验证

职责: 验证 HTML 输出完整性。
两套并行: Pydantic schema 检查 + HTML 结构检查。
"""

from pathlib import Path
import re
from report_engine.schema import StockReport


def validate_schema(report: StockReport) -> list[str]:
    """Pydantic schema 层验证"""
    issues = []
    missing = report.get_missing_required()
    if missing:
        issues.append(f'缺失强制模块: {", ".join(missing)}')

    exempted = report.get_exempted_modules()
    for e in exempted:
        issues.append(f'[豁免] {e.module_id}: {e.reason}')

    if not report.charts:
        issues.append('缺少所有图表')
    else:
        chart_ids = [c.chart_id for c in report.charts]
        for required in ['priceChart', 'scenarioChart']:
            if required not in chart_ids:
                issues.append(f'缺少强制图表: {required}')

    if not report.s7_risks or len(report.s7_risks) < 5:
        issues.append(f'S7 风险矩阵不足 5 项 (当前 {len(report.s7_risks)})')

    if report.asset_category.value in ('stock', 'hk_stock'):
        if not report.f_score_items or len(report.f_score_items) != 9:
            issues.append(f'F-Score 不足 9 项 (当前 {len(report.f_score_items)})')

    if not report.verdict:
        issues.append('缺少 Verdict 最终裁决')

    return issues


def validate_html_file(filepath: str) -> list[str]:
    """HTML 结构验证 (与原 validate_html.py 等价)"""
    issues = []
    path = Path(filepath)

    if not path.exists():
        return [f'文件不存在: {filepath}']

    html = path.read_text(encoding='utf-8')
    file_size = len(html)

    sections = re.findall(r'id="s(\d+)"', html)
    section_ids = {int(s) for s in sections}
    missing = [i for i in range(1, 9) if i not in section_ids]

    if missing:
        issues.append(f'缺失 sections: S{", S".join(map(str, missing))}')
    else:
        issues.append('8 个 section 齐全')

    if '</body>' not in html or '</html>' not in html:
        issues.append('HTML 结构不完整')

    if file_size < 15000:
        issues.append(f'文件偏小 ({file_size:,} bytes)')

    if 'id="verdict"' not in html:
        issues.append('缺少 Verdict 裁决区')

    if '<canvas' not in html:
        issues.append('缺少 Chart.js 图表')

    return issues


def validate(report: StockReport, html_path: str | None = None) -> tuple[bool, list[str]]:
    """两套并行验证"""
    all_issues = []

    schema_issues = validate_schema(report)
    all_issues.extend(f'[Schema] {i}' for i in schema_issues)

    if html_path:
        html_issues = validate_html_file(html_path)
        all_issues.extend(f'[HTML] {i}' for i in html_issues)

    passed = not any(i.startswith('[Schema] 缺失') for i in all_issues)
    return passed, all_issues
