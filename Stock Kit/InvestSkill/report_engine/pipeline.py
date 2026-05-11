"""
LangGraph 编排 — 带详细日志
用法:
  python -m report_engine.pipeline 小米
"""

import sys
import logging
import time
from pathlib import Path
from typing import TypedDict
from datetime import datetime

from langgraph.graph import StateGraph, END

from report_engine.schema import StockReport
from report_engine.stages.scaffold import scaffold
from report_engine.stages.search import run_search
from report_engine.stages.render import render_to_file
from report_engine.stages.validate import validate

BASE_DIR = Path('/home/severin/Codelib/股市分析')
LOG_DIR = BASE_DIR / '.sisyphus' / 'pipeline_logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── 日志配置 ───
log_filename = LOG_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_pipeline.log"

logger = logging.getLogger('pipeline')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler(log_filename, encoding='utf-8')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
))
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(ch)

logger.info(f"日志文件: {log_filename}")


class PipelineState(TypedDict):
    company_name: str
    report: dict
    html_path: str
    errors: list[str]
    stage: str


def stage_scaffold(state: PipelineState) -> PipelineState:
    t0 = time.time()
    logger.info(f"[Stage 0: scaffold] 开始 — {state['company_name']}")
    report = scaffold(state['company_name'])
    state['report'] = report.model_dump()
    state['stage'] = 'scaffold'
    elapsed = time.time() - t0
    logger.info(f"  Ticker={report.ticker}, Exchange={report.exchange}, Asset={report.asset_category.value}")
    logger.info(f"  Fields=cover_price={report.cover_price}, market_cap={report.cover_market_cap}")
    logger.info(f"  模块数={len(report.module_states)}")
    logger.info(f"[Stage 0: scaffold] 完成 ({elapsed:.1f}s)")
    return state


def stage_search(state: PipelineState) -> PipelineState:
    t0 = time.time()
    logger.info(f"{'='*60}")
    logger.info(f"[Stage 1+2: search+analyze] 开始")
    report = StockReport(**state['report'])
    logger.info(f"  Prompt: {report.company_name} ({report.ticker}), {report.asset_category.value}")

    try:
        report = run_search(report, logger=logger)
    except Exception as e:
        logger.error(f"  ⚠️ run_search 抛异常: {e}", exc_info=True)
        report = report

    state['report'] = report.model_dump()
    state['stage'] = 'search'

    elapsed = time.time() - t0
    logger.info(f"  结果: charts={len(report.charts)}, f_score_items={len(report.f_score_items)}")
    logger.info(f"  结果: composite_score={report.composite_score}, composite_rank={report.composite_rank_8}")
    logger.info(f"  结果: s8_signal={report.s8_signal}\n" if report.s8_signal else "  结果: s8_signal=None")
    logger.info(f"  原始 dict keys: {list(state['report'].keys())}")
    logger.info(f"[Stage 1+2: search+analyze] 完成 ({elapsed:.1f}s)")
    logger.info(f"{'='*60}")
    return state


def stage_render(state: PipelineState) -> PipelineState:
    t0 = time.time()
    logger.info(f"[Stage 3: render] 开始")
    report = StockReport(**state['report'])
    today = datetime.now().strftime('%y%m%d')
    output_dir = Path(report.company_dir) if report.company_dir else (BASE_DIR / '分析输出' / state['company_name'])
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{today}_综合分析报告.html'

    logger.info(f"  输出: {output_path}")
    logger.info(f"  序列化大小: {len(str(state['report'])):,.0f} bytes")

    path = render_to_file(report, str(output_path), logger=logger)
    state['html_path'] = str(path)
    state['stage'] = 'render'

    file_size = Path(path).stat().st_size
    elapsed = time.time() - t0
    logger.info(f"  文件大小: {file_size:,} bytes")
    logger.info(f"[Stage 3: render] 完成 ({elapsed:.1f}s)")
    return state


def stage_validate(state: PipelineState) -> PipelineState:
    t0 = time.time()
    logger.info(f"[Stage 4: validate] 开始")
    report = StockReport(**state['report'])
    passed, issues = validate(report, state.get('html_path', ''))
    state['errors'] = issues
    state['stage'] = 'validate'

    logger.info(f"  通过: {'是' if passed else '否'}")
    for i in issues:
        logger.info(f"  [{i}]")

    elapsed = time.time() - t0
    logger.info(f"[Stage 4: validate] 完成 ({elapsed:.1f}s)")
    return state


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("scaffold", stage_scaffold)
    graph.add_node("search", stage_search)
    graph.add_node("render", stage_render)
    graph.add_node("validate", stage_validate)

    graph.set_entry_point("scaffold")
    graph.add_edge("scaffold", "search")
    graph.add_edge("search", "render")
    graph.add_edge("render", "validate")
    graph.add_edge("validate", END)

    return graph.compile()


def run(company_name: str):
    logger.info(f"Pipeline 启动: {company_name}")
    t_pipeline_start = time.time()

    app = build_graph()
    initial = PipelineState(company_name=company_name, report={}, html_path='', errors=[], stage='init')

    try:
        result = app.invoke(initial)
    except Exception as e:
        logger.error(f"Pipeline 崩溃: {e}", exc_info=True)
        raise

    total_elapsed = time.time() - t_pipeline_start
    logger.info(f"总耗时: {total_elapsed:.1f}s")

    print(f'\n{"="*60}')
    ok = not any('缺失' in e for e in result.get('errors', []))
    print(f'{"✅ 完成" if ok else "⚠️ 部分完成"} — {company_name}')
    print(f'HTML: {result.get("html_path", "未生成")}')
    print(f'日志: {log_filename}')
    if result.get('errors'):
        print('\n问题:')
        for e in result['errors']:
            print(f'  {e}')
    print(f'{"="*60}')

    logger.info(f"Pipeline 结束: {'成功' if ok else '部分完成'}, 总耗时 {total_elapsed:.1f}s")
    return result


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('用法: python -m report_engine.pipeline <公司名>')
        sys.exit(1)
    run(sys.argv[1])
