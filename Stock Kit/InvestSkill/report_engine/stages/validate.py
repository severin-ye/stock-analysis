"""Stage 4: 验证

职责: 验证 HTML 输出完整性 + 数据真实性交叉验证。
三套并行: Pydantic schema 检查 + HTML 结构检查 + 数据真实性交叉验证。
"""

from pathlib import Path
import json
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


def validate(report: StockReport | None = None, html_path: str | None = None) -> tuple[bool, list[str]]:
    """三套并行验证"""
    all_issues = []

    if report is not None:
        schema_issues = validate_schema(report)
        all_issues.extend(f'[Schema] {i}' for i in schema_issues)

    if html_path:
        html_issues = validate_html_file(html_path)
        all_issues.extend(f'[HTML] {i}' for i in html_issues)

        data_issues = validate_data_sanity(html_path)
        all_issues.extend(f'[Data] {i}' for i in data_issues)

    passed = not any(
        i.startswith('[Schema] 缺失')
        or (i.startswith('[Data] ') and '校验通过' not in i and '跳过' not in i)
        for i in all_issues
    )
    return passed, all_issues


def validate_data_sanity(html_path: str) -> list[str]:
    """数据真实性交叉验证: 提取 HTML 价格/市值, 对比 prices.json 基准"""
    issues = []
    html = Path(html_path)

    if not html.exists():
        return [f'文件不存在: {html_path}']

    content = html.read_text(encoding='utf-8')

    prices_path = html.parent.parent.parent.parent / 'Stock Kit' / 'data' / 'prices.json'
    if not prices_path.exists():
        prices_path = Path(__file__).parent.parent.parent.parent / 'data' / 'prices.json'
    if not prices_path.exists():
        return ['[跳过] prices.json 未找到, 无法交叉验证数据']

    try:
        prices_data = json.loads(prices_path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return ['[跳过] prices.json 读取失败']

    # 尝试 JSON 格式 (report_engine pipeline)
    price_match = re.search(r'cover_price["\s:]+(\$?[\d,.]+)', content, re.IGNORECASE)
    ticker_match = re.search(r'"ticker"\s*:\s*"(\w+)"', content)

    # 回退: HTML 内联格式 (tools/pipeline Jinja2 渲染)
    if not price_match:
        price_match = re.search(r'当前价格[：:]\s*\$?([\d,.]+)', content)
    if not price_match:
        price_match = re.search(r'class="(?:up|dn|neut)">\$?([\d,.]+)</span>', content)
    if not ticker_match:
        ticker_match = re.search(r'<div class="ticker">(\w+)</div>', content)
    if not ticker_match:
        ticker_match = re.search(r'<title>(\w+)\s*[—–-]', content)

    if not price_match:
        issues.append('HTML 中找不到 cover_price 价格')
    if not ticker_match:
        issues.append('HTML 中找不到 ticker 字段')

    if price_match and ticker_match:
        html_price_str = price_match.group(1).replace('$', '').replace(',', '')
        ticker = ticker_match.group(1).upper()

        try:
            html_price = float(html_price_str)
        except ValueError:
            issues.append(f'cover_price 无法解析为数字: {html_price_str}')
            html_price = None

        if html_price is not None:
            actual = _find_price_in_cache(prices_data, ticker)
            if actual:
                diff_pct = abs(html_price - actual) / actual * 100
                if diff_pct > 5:
                    issues.append(
                        f'价格异常偏差: HTML={html_price:.2f}, '
                        f'prices.json={actual:.2f}, 偏差={diff_pct:.1f}% (>5%)'
                    )
                else:
                    issues.append(f'价格校验通过: HTML={html_price:.2f} vs prices.json={actual:.2f} ({diff_pct:.1f}%)')

    pe_match = re.search(r'Forward P/E["\s:]+([\d.]+)', content)
    if pe_match and pe_match.group(1) in ('0', '0.0', '-0'):
        issues.append('Forward P/E 为 0, 疑似假数据')

    roic_match = re.search(r'ROIC["\s:]+([\d.]+%)', content)
    if roic_match and roic_match.group(1) == '0%':
        issues.append('ROIC 为 0%, 疑似未填充')

    return issues


def _find_price_in_cache(prices_data: dict, ticker: str) -> float | None:
    """从 prices.json 查找标的实时价格 (兼容 dict-of-records 和 list-of-records)"""
    # Case 1: dict-of-records (top-level keys = tickers)
    if isinstance(prices_data, dict) and ticker.upper() in (k.upper() for k in prices_data):
        for k, v in prices_data.items():
            if k.upper() == ticker.upper() and isinstance(v, dict):
                for key in ('price', 'latest_price', 'current_price'):
                    val = v.get(key)
                    if isinstance(val, (int, float)) and val > 0:
                        return float(val)

    # Case 2: dict with 'records' key (list of records)
    records = prices_data.get('records', []) if isinstance(prices_data, dict) else None
    if not isinstance(records, list) and isinstance(prices_data, list):
        records = prices_data
    if isinstance(records, list):
        for r in records:
            if isinstance(r, dict):
                if r.get('ticker', '').upper() == ticker or r.get('symbol', '').upper() == ticker:
                    for key in ('price', 'latest_price', 'current_price'):
                        val = r.get(key)
                        if isinstance(val, (int, float)) and val > 0:
                            return float(val)
    return None
