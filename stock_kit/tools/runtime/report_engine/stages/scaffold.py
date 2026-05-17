"""Stage 0: 脚手架

职责: 识别公司、生成报告壳、初始化模块状态。
纯 Python，不需要 LLM。

公司映射从 company_registry 统一读取 (Single Source of Truth)。
别名 (如 "Solana"→"索拉纳") 在此模块处理，不污染 registry。
"""

import os
from pathlib import Path
from datetime import datetime
from tools.runtime.report_engine.schema import (
    StockReport, ModuleState, ModuleStatus, ModuleDef,
    AssetCategory, ALL_MODULES
)
from tools.company_registry import name_zh_to_tuple

_ALIASES: dict[str, str] = {
    'Solana': '索拉纳',
}

BASE_DIR = Path(os.environ.get('STOCK_ANALYSIS_HOME', str(Path(__file__).resolve().parents[5])))
OUTPUT_DIR = BASE_DIR / '分析输出'


def scaffold(company_name: str) -> StockReport:
    company_dir = OUTPUT_DIR / company_name
    if not company_dir.exists():
        company_dir.mkdir(parents=True, exist_ok=True)

    resolved = _ALIASES.get(company_name, company_name)
    ticker, name_en, exchange, sector, category = name_zh_to_tuple()[resolved]
    today = datetime.now().strftime('%y%m%d')

    report = StockReport(
        ticker=ticker,
        company_name=company_name,
        company_name_en=name_en,
        exchange=exchange,
        sector=sector,
        asset_category=category,
        report_date=datetime.now().strftime('%Y-%m-%d'),
        data_date=f'{datetime.now().strftime("%Y-%m-%d")} 收盘',
        company_dir=str(company_dir),
        cover_title=f'{ticker} — {company_name} 综合投资分析',
    )

    applicable = [m for m in ALL_MODULES if category in m.asset_categories]
    for mod in applicable:
        report.module_states[mod.module_id] = ModuleState(
            module_id=mod.module_id,
            status=ModuleStatus.MISSING,
            data=None,
        )

    return report