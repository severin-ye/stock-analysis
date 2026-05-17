"""公司注册表 — 单一来源 (Single Source of Truth)

所有公司映射从此模块统一派生，其他文件不再维护独立映射。
新增公司只需编辑 data/companies.json，所有消费者自动同步。

提供:
  - REGISTRY: 原始 JSON 数据 dict
  - 派生映射: name_zh_to_ticker, name_zh_to_tuple, ticker_to_name_zh, ticker_to_info 等
  - 市场分组: MARKET_GROUPS (从 asset_category 自动分组)
  - 加密专用: CRYPTO_ID_MAP, DEFILLAMA_CHAIN_MAP, YF_CRYPTO_MAP
  - yfinance: YF_TICKER_MAP, YF_STOCK_SYMBOLS
"""

import json
from enum import Enum
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'
COMPANIES_JSON = DATA_DIR / 'companies.json'


class AssetCategory(str, Enum):
    STOCK = 'stock'
    HK_STOCK = 'hk_stock'
    CRYPTO = 'crypto'


_REGISTRY: dict = {}


def _load() -> dict:
    if not _REGISTRY:
        raw = json.loads(COMPANIES_JSON.read_text(encoding='utf-8'))
        for ticker, entry in raw.items():
            entry['ticker'] = ticker
            entry['asset_category'] = AssetCategory(entry['asset_category'])
            _REGISTRY[ticker] = entry
    return _REGISTRY


def registry() -> dict:
    return _load()


def name_zh_to_ticker() -> dict[str, str]:
    return {e['name_zh']: t for t, e in registry().items()}


def name_zh_to_tuple() -> dict[str, tuple]:
    return {
        e['name_zh']: (t, e['name_en'], e['exchange'], e['sector'], e['asset_category'])
        for t, e in registry().items()
    }


def ticker_to_name_zh() -> dict[str, str]:
    return {t: e['name_zh'] for t, e in registry().items()}


def ticker_to_info() -> dict[str, tuple[str, str]]:
    return {t: (e['exchange'], e['name_zh']) for t, e in registry().items()}


def ticker_to_stock_registry() -> dict[str, tuple[str, str, str]]:
    return {
        t: (e.get('gf_code', t), e['exchange'], e['market'])
        for t, e in registry().items()
        if e['asset_category'] != AssetCategory.CRYPTO
    }


def yf_ticker_map() -> dict[str, str]:
    return {e['yf_ticker']: t for t, e in registry().items()}


def yf_stock_symbols() -> list[str]:
    return [
        e['yf_ticker'] for t, e in registry().items()
        if e['asset_category'] != AssetCategory.CRYPTO
    ]


CRYPTO_ID_MAP: dict[str, str] = {
    t: e['crypto_id'] for t, e in registry().items()
    if 'crypto_id' in e
}

DEFILLAMA_CHAIN_MAP: dict[str, str] = {
    t: e['defillama_chain'] for t, e in registry().items()
    if 'defillama_chain' in e
}

MARKET_GROUPS: dict[str, list[str]] = {
    '🇺🇸 美股': [t for t, e in registry().items() if e['market'] == 'US'],
    '🇭🇰 港股': [t for t, e in registry().items() if e['market'] == 'HK'],
    '🇯🇵 日股': [t for t, e in registry().items() if e['market'] == 'JP'],
    '🇰🇷 韩股': [t for t, e in registry().items() if e['market'] == 'KR'],
    '🇨🇳 A股': [t for t, e in registry().items() if e['market'] == 'CN'],
    '₿ 加密': [t for t, e in registry().items() if e['market'] == 'Crypto'],
}


def get_by_name_zh(name: str) -> dict | None:
    r = registry()
    for t, e in r.items():
        if e['name_zh'] == name:
            return e
    return None


def get_ticker_by_name_zh(name: str) -> str | None:
    e = get_by_name_zh(name)
    return e['ticker'] if e else None
