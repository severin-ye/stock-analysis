#!/usr/bin/env python3
"""验证 HTML 综合分析报告完整性

检查项:
  1. 8 个 section (s1-s8) 是否齐全
  2. HTML 结构是否完整 (</body></html>)
  3. 文件大小是否合理 (>15KB)
  4. 关键元素是否存在 (verdict, 图表等)

用法:
  python3 validate_html.py <html文件路径>
  python3 validate_html.py --all    # 验证所有报告
"""

import re
import sys
import os
from glob import glob


def validate_report(filepath):
    """验证单个报告，返回 (passed, issues)"""
    issues = []

    if not os.path.exists(filepath):
        return False, [f'文件不存在: {filepath}']

    with open(filepath, 'r') as f:
        html = f.read()

    file_size = len(html)

    # 1. Section 完整性
    sections = re.findall(r'id="s(\d+)"', html)
    section_ids = set(int(s) for s in sections)
    missing = [i for i in range(1, 9) if i not in section_ids]

    if missing:
        issues.append(f'缺失 sections: S{", S".join(map(str, missing))}')
    elif len(sections) < 8:
        issues.append(f'Section 数量不足: 找到 {len(sections)}')
    else:
        issues.append(f'✅ 8 个 section 齐全')

    # 2. HTML 结构
    if '</body>' not in html or '</html>' not in html:
        issues.append('❌ HTML 结构不完整（缺少 </body> 或 </html>）')

    # 3. 文件大小
    if file_size < 15000:
        issues.append(f'⚠️ 文件偏小 ({file_size:,} bytes)，可能内容不完整')
    else:
        issues.append(f'✅ 文件大小正常 ({file_size:,} bytes)')

    # 4. 关键元素
    if 'id="verdict"' not in html:
        issues.append('❌ 缺少 Verdict 裁决区')

    if '<canvas' not in html:
        issues.append('⚠️ 缺少 Chart.js 图表')

    if 'InvestSkill' not in html:
        issues.append('⚠️ 缺少 InvestSkill 标识')

    passed = all(not i.startswith('❌') for i in issues)
    return passed, issues


def main():
    if len(sys.argv) < 2:
        print('用法: python3 validate_html.py <文件路径>')
        print('      python3 validate_html.py --all')
        sys.exit(1)

    if sys.argv[1] == '--all':
        base = '/home/severin/Codelib/股市分析'
        reports = glob(f'{base}/*/2*综合分析报告.html')
        reports += glob(f'{base}/*/2*_综合分析报告.html')

        all_passed = True
        for r in sorted(reports):
            passed, issues = validate_report(r)
            name = os.path.relpath(r, base)
            status = '✅' if passed else '❌'
            print(f'\n{status} {name}')
            for issue in issues:
                issue_icon = issue[:2] if issue[0] in '✅⚠❌' else ' '
                print(f'   {issue}')
            if not passed:
                all_passed = False

        print(f'\n{"="*50}')
        print(f'总计: {len(reports)} 个报告')
        if all_passed:
            print('✅ 全部通过')
        else:
            print('❌ 存在不合格报告')
        sys.exit(0 if all_passed else 1)

    else:
        filepath = sys.argv[1]
        passed, issues = validate_report(filepath)
        for issue in issues:
            print(issue)
        sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
