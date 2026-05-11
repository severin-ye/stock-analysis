"""HTML 验证器 — 检查报告完整性 (8 sections, verdict, charts)"""

import re
from pathlib import Path


def validate_html_file(filepath: str) -> tuple[bool, list[str]]:
    """验证 HTML 文件结构"""
    issues = []
    path = Path(filepath)

    if not path.exists():
        return False, [f"文件不存在: {filepath}"]

    html = path.read_text(encoding='utf-8')
    file_size = len(html)

    sections = re.findall(r'id="s(\d+)"', html)
    section_ids = {int(s) for s in sections}
    missing = [i for i in range(1, 9) if i not in section_ids]

    if missing:
        issues.append(f"缺失 sections: S{', S'.join(map(str, missing))}")
    else:
        issues.append("8 个 section 齐全")

    if '</body>' not in html or '</html>' not in html:
        issues.append("HTML 结构不完整")

    if file_size < 15000:
        issues.append(f"文件偏小 ({file_size:,} bytes)")

    if 'id="verdict"' not in html:
        issues.append("缺少 Verdict 裁决区")

    if '<canvas' not in html:
        issues.append("缺少 Chart.js 图表")

    script_start = html.find('<script>')
    if script_start != -1:
        script_region = html[script_start:]
        entities = script_region.count('&#34;') + script_region.count('&#39;')
        if entities > 0:
            issues.append(f"<script> 中有 {entities} 处 HTML 实体 — 图表可能不渲染!")

    passed = len([i for i in issues if '缺失' in i or '不完整' in i]) == 0
    return passed, issues
