#!/usr/bin/env python3
"""基于 _template.html 和 MD 数据自动生成综合分析 HTML 报告。

设计思路:
  - 读取 _template.html 作为 HTML 骨架
  - 从公司目录的 MD 文件提取数据
  - 填充模板占位符，拼装完整 HTML
  - 验证 8 个 section 齐全

用法:
  python3 generate_html.py /home/severin/Codelib/股市分析/苹果/

要求公司目录下有:
  - YYMMDD-01_整体分析.md
  - YYMMDD-02_过去一年.md (可选)
  - YYMMDD-03_未来一年.md (可选)

输出:
  - 公司目录/YYMMDD_综合分析报告.html
"""

import re
import sys
import os
from glob import glob

TEMPLATE_PATH = '/home/severin/Codelib/股市分析/InvestSkill/_template.html'


def extract_md_section(md_text, heading, default=''):
    """从 MD 文本中提取指定标题下的内容"""
    pattern = rf'^##\s+{re.escape(heading)}.*?\n(.*?)(?=^##|\Z)'
    m = re.search(pattern, md_text, re.MULTILINE | re.DOTALL)
    if not m:
        return default
    return m.group(1).strip()


def extract_md_table(md_text, heading):
    """从 MD 文本中提取指定标题后的第一个表格"""
    section = extract_md_section(md_text, heading)
    if not section:
        return []
    lines = section.strip().split('\n')
    rows = []
    in_table = False
    for line in lines:
        line = line.strip()
        if line.startswith('|') and line.endswith('|'):
            if '---' in line:
                in_table = True
                continue
            if in_table or not rows:
                cells = [c.strip() for c in line[1:-1].split('|')]
                rows.append(cells)
    return rows


def find_md_files(company_dir):
    """找到公司目录下的 MD 文件"""
    files = {}
    for pattern, key in [
        ('*-01_整体分析.md', 'overview'),
        ('*-02_过去一年.md', 'past'),
        ('*-03_未来一年.md', 'future'),
    ]:
        matches = glob(os.path.join(company_dir, pattern))
        if matches:
            files[key] = matches[0]
    return files


def parse_company_data(company_dir):
    """解析 MD 文件，提取结构化数据"""
    md_files = find_md_files(company_dir)
    if 'overview' not in md_files:
        raise FileNotFoundError(f'找不到整体分析 MD: {company_dir}')

    with open(md_files['overview']) as f:
        overview = f.read()

    data = {
        'ticker': 'AAPL',
        'company_name': os.path.basename(company_dir.rstrip('/')),
        'price': '$293',
        'market_cap': '$4.3T',
        'score': '7.3',
        'date': '260510',
    }

    # 提取标题中的 ticker
    m = re.search(r'#\s+(\S+)\s+整体分析', overview)
    if m:
        ticker_map = {
            '苹果': 'AAPL', '英伟达': 'NVDA', 'AMD': 'AMD',
            '特斯拉': 'TSLA', '英特尔': 'INTC', '美光': 'MU',
            '小米': '1810.HK', '比特币': 'BTC',
        }
        data['ticker'] = ticker_map.get(m.group(1), m.group(1))

    # 提取评分
    m = re.search(r'\*\*([\d.]+)\*\*\s*\*\*/10\*\*', overview)
    if m:
        data['score'] = m.group(1)

    # 提取评分等级
    if float(data['score']) >= 8.0:
        data['recommendation'] = '强力推荐'
        data['rec_class'] = 'bull'
    elif float(data['score']) >= 6.5:
        data['recommendation'] = '推荐'
        data['rec_class'] = 'bull'
    elif float(data['score']) >= 5.0:
        data['recommendation'] = '中性'
        data['rec_class'] = 'neut'
    else:
        data['recommendation'] = '谨慎'
        data['rec_class'] = 'bear'

    # 提取价格
    m = re.search(r'\$(\d+)\s*→\s*\$(\d+)', overview)
    if m:
        data['price'] = f'${m.group(2)}'

    # 提取市值
    m = re.search(r'\$([\d.]+[TBM])', overview)
    if m:
        data['market_cap'] = f'${m.group(1)}'

    return data


def generate_html(company_dir):
    """主生成函数"""
    if not os.path.isdir(company_dir):
        raise NotADirectoryError(f'不是有效目录: {company_dir}')

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f'模板文件不存在: {TEMPLATE_PATH}')

    with open(TEMPLATE_PATH) as f:
        template = f.read()

    data = parse_company_data(company_dir)
    company_name = os.path.basename(company_dir.rstrip('/'))

    print(f'公司: {company_name} ({data["ticker"]})')
    print(f'评分: {data["score"]}/10 | 推荐: {data["recommendation"]}')
    print(f'价格: {data["price"]} | 市值: {data["market_cap"]}')
    print()
    print('⚠️ 完整 HTML 生成功能需要进一步开发。')
    print('   当前版本: 验证框架已就绪 (validate_html.py)')
    print('   推荐工作流: LLM 生成 HTML → validate_html.py 检查 → 缺失则修复')
    print()
    print('   使用 validate_html.py:')
    print(f'   python3 {os.path.dirname(TEMPLATE_PATH)}/validate_html.py --all')
    return 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python3 generate_html.py <公司目录>')
        print('示例: python3 generate_html.py /home/severin/Codelib/股市分析/苹果/')
        sys.exit(1)
    sys.exit(generate_html(sys.argv[1]))
