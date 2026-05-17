"""批量并行分析 — 多公司同时执行，上下文完全隔离

使用 multiprocessing 实现真正的进程隔离，每个公司独立的:
- scaffold → fetch → rank → LLM → render → validate

用法:
    from stock_analysis.batch import run_batch_analysis
    results = run_batch_analysis(["英伟达", "苹果", "特斯拉"])
"""

import logging
import multiprocessing as mp
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# 确保项目根目录在 path 中（子进程需要）
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent
if str(_project_root / "src") not in sys.path:
    sys.path.insert(0, str(_project_root / "src"))


@dataclass
class BatchResult:
    """单个公司的分析结果"""

    company_name: str
    ticker: str = ""
    html_path: Optional[str] = None
    success: bool = False
    elapsed_seconds: float = 0.0
    error: Optional[str] = None
    composite_score: Optional[float] = None
    composite_rank: Optional[str] = None
    score_10: Optional[float] = None
    f_score: Optional[int] = None
    price: Optional[float] = None
    ebit_ev: Optional[str] = None
    roic: Optional[str] = None
    peg: Optional[str] = None
    signal: Optional[str] = None
    action: Optional[str] = None
    log_file: Optional[str] = None


@dataclass
class BatchSummary:
    """批次汇总"""

    batch_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    results: list[BatchResult] = field(default_factory=list)
    total_elapsed: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_elapsed": self.total_elapsed,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "results": [
                {
                    "company_name": r.company_name,
                    "ticker": r.ticker,
                    "html_path": r.html_path,
                    "success": r.success,
                    "elapsed_seconds": r.elapsed_seconds,
                    "error": r.error,
                    "composite_score": r.composite_score,
                    "composite_rank": r.composite_rank,
                    "score_10": r.score_10,
                    "f_score": r.f_score,
                    "price": r.price,
                    "ebit_ev": r.ebit_ev,
                    "roic": r.roic,
                    "peg": r.peg,
                    "signal": r.signal,
                    "action": r.action,
                }
                for r in self.results
            ],
        }


def _run_single_analysis(company_name: str, dry_run: bool = False, use_opencode_llm: bool = False) -> BatchResult:
    """在独立进程中运行单个公司的完整分析

    每个进程有完全独立的内存空间，上下文不共享。
    """
    t0 = time.time()
    result = BatchResult(company_name=company_name)

    try:
        # 在子进程中重新导入（确保隔离）
        from stock_analysis.cli import run_analysis
        from stock_analysis.registry import name_zh_to_ticker

        # 获取 ticker
        ticker = name_zh_to_ticker().get(company_name, "")
        result.ticker = ticker

        # 运行完整分析
        html_path = run_analysis(company_name, dry_run=dry_run, use_opencode_llm=use_opencode_llm)

        result.elapsed_seconds = time.time() - t0
        result.html_path = html_path
        result.success = html_path is not None

        # 尝试提取关键指标（用于汇总页）
        if html_path:
            _extract_metrics_from_html(result, html_path)

    except Exception as e:
        result.elapsed_seconds = time.time() - t0
        result.error = f"{type(e).__name__}: {str(e)[:500]}"
        result.success = False

    return result


def _extract_metrics_from_html(result: BatchResult, html_path: str) -> None:
    """从生成的 HTML 中提取关键指标（轻量级解析）"""
    try:
        html_content = Path(html_path).read_text(encoding="utf-8")
        import re

        # 提取综合排名
        rank_match = re.search(r'综合\s*#(\d+/\d+)', html_content)
        if rank_match:
            result.composite_rank = rank_match.group(1)

        # 提取十分制评分
        score_match = re.search(r'(\d+\.\d+)/10', html_content)
        if score_match:
            result.score_10 = float(score_match.group(1))

        # 提取 F-Score
        fscore_match = re.search(r'F-Score[:\s]*(\d+)/9', html_content)
        if fscore_match:
            result.f_score = int(fscore_match.group(1))

        # 提取价格
        price_match = re.search(r'当前股价?[:\s]*[$¥€]?([\d,\.]+)', html_content)
        if price_match:
            result.price = float(price_match.group(1).replace(',', ''))

        # 提取信号
        signal_match = re.search(r'Signal[:\s]*(BULLISH|NEUTRAL|BEARISH)', html_content, re.IGNORECASE)
        if signal_match:
            result.signal = signal_match.group(1).upper()

        # 提取 action
        action_match = re.search(r'Action[:\s]*(BUY|HOLD|SELL)', html_content, re.IGNORECASE)
        if action_match:
            result.action = action_match.group(1).upper()

        # 提取 EBIT/EV
        ebit_ev_match = re.search(r'EBIT/EV[:\s]*([\d\.%\-—]+)', html_content)
        if ebit_ev_match:
            result.ebit_ev = ebit_ev_match.group(1)

        # 提取 ROIC
        roic_match = re.search(r'ROIC[:\s]*([\d\.%\-—]+)', html_content)
        if roic_match:
            result.roic = roic_match.group(1)

        # 提取 PEG
        peg_match = re.search(r'PEG[:\s]*([\d\.%\-—xX]+)', html_content)
        if peg_match:
            result.peg = peg_match.group(1)

    except Exception:
        pass


def run_batch_analysis(
    company_names: list[str],
    dry_run: bool = False,
    use_opencode_llm: bool = False,
    max_workers: Optional[int] = None,
) -> BatchSummary:
    """并行分析多家公司

    Args:
        company_names: 公司中文名列表
        dry_run: 是否跳过 LLM 调用
        use_opencode_llm: 是否使用 OpenCode LLM
        max_workers: 最大并行进程数（默认 CPU 核心数）

    Returns:
        BatchSummary: 批次分析结果汇总
    """
    if not company_names:
        raise ValueError("company_names 不能为空")

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = BatchSummary(batch_id=batch_id, start_time=datetime.now())

    print(f"🚀 批量分析启动: {len(company_names)} 家公司")
    print(f"   公司: {', '.join(company_names)}")
    print(f"   并行度: {max_workers or mp.cpu_count()} 进程")
    print(f"   批次ID: {batch_id}")
    print("-" * 60)

    t0 = time.time()

    # 使用进程池实现真正的隔离
    # 每个公司一个进程，上下文完全独立
    if max_workers is None:
        max_workers = min(len(company_names), mp.cpu_count())

    results = []
    with mp.Pool(processes=max_workers) as pool:
        # 异步提交所有任务
        async_results = [
            pool.apply_async(_run_single_analysis, (name, dry_run, use_opencode_llm))
            for name in company_names
        ]

        # 收集结果（带进度显示）
        for i, ar in enumerate(async_results, 1):
            try:
                result = ar.get(timeout=600)  # 10分钟超时
                results.append(result)
                status = "✅" if result.success else "❌"
                print(f"[{i}/{len(company_names)}] {status} {result.company_name} ({result.elapsed_seconds:.1f}s)")
                if result.error:
                    print(f"      错误: {result.error[:200]}")
            except Exception as e:
                print(f"[{i}/{len(company_names)}] ❌ {company_names[i-1]} (超时/异常: {e})")
                results.append(
                    BatchResult(
                        company_name=company_names[i - 1],
                        success=False,
                        error=f"Pool timeout: {e}",
                    )
                )

    summary.results = results
    summary.end_time = datetime.now()
    summary.total_elapsed = time.time() - t0
    summary.success_count = sum(1 for r in results if r.success)
    summary.failure_count = len(results) - summary.success_count

    # 生成汇总页
    _generate_batch_summary_html(summary)

    # 保存 JSON 汇总
    _save_batch_summary_json(summary)

    print("-" * 60)
    print(f"✅ 批量分析完成: {summary.success_count}/{len(company_names)} 成功")
    print(f"   总耗时: {summary.total_elapsed:.1f}s")
    print(f"   汇总页: 分析输出/批次汇总/{summary.batch_id}_汇总报告.html")

    return summary


def _generate_batch_summary_html(summary: BatchSummary) -> str:
    """生成批次汇总 HTML 页"""
    from stock_analysis.registry import ticker_to_name_zh

    name_map = ticker_to_name_zh()

    # 按综合排名排序
    sorted_results = sorted(
        summary.results,
        key=lambda r: (r.score_10 or 0, r.company_name),
        reverse=True,
    )

    # 构建对比表格行
    rows_html = []
    for i, r in enumerate(sorted_results, 1):
        signal_color = {
            "BULLISH": "#059669",
            "NEUTRAL": "#d97706",
            "BEARISH": "#dc2626",
        }.get(r.signal or "", "#64748b")

        action_color = {
            "BUY": "#059669",
            "HOLD": "#d97706",
            "SELL": "#dc2626",
        }.get(r.action or "", "#64748b")

        rows_html.append(
            f"""
        <tr>
            <td><strong>#{i}</strong></td>
            <td><a href="../{r.company_name}/{Path(r.html_path).name if r.html_path else ''}">{r.company_name}</a> <small>{r.ticker}</small></td>
            <td>{r.score_10 or '—'}/10</td>
            <td>{r.composite_rank or '—'}</td>
            <td>{r.f_score or '—'}/9</td>
            <td>{r.ebit_ev or '—'}</td>
            <td>{r.roic or '—'}</td>
            <td>{r.peg or '—'}</td>
            <td style="color:{signal_color};font-weight:700">{r.signal or '—'}</td>
            <td style="color:{action_color};font-weight:700">{r.action or '—'}</td>
            <td>{r.elapsed_seconds:.1f}s</td>
            <td>{'✅' if r.success else '❌'}</td>
        </tr>
"""
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>批次分析汇总 — {summary.batch_id}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--navy:#0f172a;--blue:#2563eb;--green:#059669;--red:#dc2626;--amber:#d97706;--slate:#64748b;--border:#e2e8f0;--bg:#f8fafc;--white:#fff}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Inter','PingFang SC',sans-serif;background:var(--bg);color:var(--navy);font-size:14px;line-height:1.6}}
.wrap{{max-width:1200px;margin:0 auto;padding:40px 24px}}
h1{{font-size:28px;font-weight:800;margin-bottom:4px}}
.sub{{font-size:13px;color:var(--slate);margin-bottom:32px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:32px}}
.stat-card{{background:var(--white);border:1px solid var(--border);border-radius:8px;padding:20px;text-align:center}}
.stat-card .num{{font-size:36px;font-weight:800;color:var(--blue)}}
.stat-card .label{{font-size:12px;color:var(--slate);margin-top:4px}}
table{{width:100%;border-collapse:collapse;background:var(--white);border:1px solid var(--border);border-radius:8px;overflow:hidden}}
th{{background:#f1f5f9;padding:12px 16px;text-align:left;font-size:11px;font-weight:600;color:var(--slate);text-transform:uppercase;letter-spacing:.5px}}
td{{padding:12px 16px;border-bottom:1px solid #f1f5f9}}
tr:hover td{{background:#fafbff}}
tr:last-child td{{border-bottom:none}}
a{{color:var(--blue);text-decoration:none}}
a:hover{{text-decoration:underline}}
footer{{text-align:center;padding:32px 0;font-size:11px;color:var(--slate);margin-top:40px;border-top:1px solid var(--border)}}
</style>
</head>
<body>
<div class="wrap">
<h1>📊 批次分析汇总</h1>
<p class="sub">批次 ID: {summary.batch_id} · {summary.start_time.strftime('%Y-%m-%d %H:%M')} · Greenblatt 四层加权排名</p>

<div class="stats">
    <div class="stat-card"><div class="num">{len(summary.results)}</div><div class="label">分析公司数</div></div>
    <div class="stat-card"><div class="num">{summary.success_count}</div><div class="label">成功</div></div>
    <div class="stat-card"><div class="num">{summary.failure_count}</div><div class="label">失败</div></div>
    <div class="stat-card"><div class="num">{summary.total_elapsed:.1f}s</div><div class="label">总耗时</div></div>
</div>

<table>
<thead>
<tr>
    <th>排名</th>
    <th>公司</th>
    <th>十分制</th>
    <th>综合排名</th>
    <th>F-Score</th>
    <th>EBIT/EV</th>
    <th>ROIC</th>
    <th>PEG</th>
    <th>信号</th>
    <th>建议</th>
    <th>耗时</th>
    <th>状态</th>
</tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>

<footer>InvestSkill v3.1 · 批次分析汇总 · 教育性分析，不构成投资建议</footer>
</div>
</body>
</html>"""

    output_dir = Path(os.environ.get("STOCK_ANALYSIS_HOME", str(_project_root))) / "分析输出" / "批次汇总"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{summary.batch_id}_汇总报告.html"
    output_path.write_text(html, encoding="utf-8")

    return str(output_path)


def _save_batch_summary_json(summary: BatchSummary) -> str:
    """保存 JSON 格式汇总"""
    import json

    output_dir = Path(os.environ.get("STOCK_ANALYSIS_HOME", str(_project_root))) / "分析输出" / "批次汇总"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{summary.batch_id}_汇总数据.json"
    output_path.write_text(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


if __name__ == "__main__":
    # 测试用法
    import sys

    if len(sys.argv) > 1:
        companies = sys.argv[1:]
        run_batch_analysis(companies)
    else:
        print("Usage: python -m stock_analysis.batch <公司1> <公司2> ...")
