"""Stage 0: 脚手架

职责: 识别公司、生成报告壳、初始化模块状态。
纯 Python，不需要 LLM。
"""

from pathlib import Path
from datetime import datetime
from report_engine.schema import (
    StockReport, ModuleState, ModuleStatus, ModuleDef,
    AssetCategory, ALL_MODULES
)

# ticker 映射
TICKER_MAP = {
    '苹果': ('AAPL', 'Apple', 'NASDAQ', '科技硬件', AssetCategory.STOCK),
    '英伟达': ('NVDA', 'NVIDIA', 'NASDAQ', '半导体', AssetCategory.STOCK),
    'AMD': ('AMD', 'AMD', 'NASDAQ', '半导体', AssetCategory.STOCK),
    '特斯拉': ('TSLA', 'Tesla', 'NASDAQ', '汽车/科技', AssetCategory.STOCK),
    '英特尔': ('INTC', 'Intel', 'NASDAQ', '半导体', AssetCategory.STOCK),
    '美光': ('MU', 'Micron', 'NASDAQ', '半导体', AssetCategory.STOCK),
    '小米': ('1810.HK', 'Xiaomi', 'HKEX', '科技硬件', AssetCategory.HK_STOCK),
    '比特币': ('BTC', 'Bitcoin', 'Crypto', '加密货币', AssetCategory.CRYPTO),
}

BASE_DIR = Path('/home/severin/Codelib/股市分析')


def scaffold(company_name: str) -> StockReport:
    company_dir = BASE_DIR / company_name
    if not company_dir.exists():
        raise FileNotFoundError(f'公司目录不存在: {company_dir}')

    ticker, name_en, exchange, sector, category = TICKER_MAP[company_name]
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
