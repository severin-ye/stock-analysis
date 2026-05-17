"""多市场数据定义: Google Finance URL 模板 + 解析器 + 加密 API

本模块定义:
  1. 各市场 Google Finance URL 模板
  2. 正则解析器 (将 webfetch 返回的文本 → PriceSnapshot 字段)
  3. CoinGecko / DeFiLlama API 端点
  4. 币种汇率映射

公司映射从 company_registry 统一读取 (Single Source of Truth)。
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from tools.company_registry import ticker_to_stock_registry

DATA_DIR = Path(__file__).parent.parent / 'data'
COMPANIES_JSON = DATA_DIR / 'companies.json'

# ──────────────────────────────────────────
# Google Finance URL 模板
# ──────────────────────────────────────────

GF_URL_TEMPLATE = "https://www.google.com/finance/quote/{code}:{exchange}"

# 交易所代码 → Google Finance 后缀
EXCHANGE_TO_GF: dict[str, str] = {
    'NASDAQ': 'NASDAQ',
    'NYSE': 'NYSE',
    'HKEX': 'HKG',
    'TSE': 'TYO',
    'KOSPI': 'KRX',
    'KOSDAQ': 'KOSDAQ',
    'SSE': 'SHA',
}

STOCK_REGISTRY: dict[str, tuple[str, str, str]] = ticker_to_stock_registry()

# 币种 → 符号/代码
CURRENCY_MAP: dict[str, dict[str, str]] = {
    'US': {'symbol': '$', 'code': 'USD'},
    'HK': {'symbol': 'HK$', 'code': 'HKD'},
    'JP': {'symbol': '¥', 'code': 'JPY'},
    'KR': {'symbol': '₩', 'code': 'KRW'},
    'CN': {'symbol': '¥', 'code': 'CNY'},
}


# ──────────────────────────────────────────
# 多市场数据源矩阵
# ──────────────────────────────────────────

@dataclass(frozen=True)
class SourceSpec:
    """单个数据源的用途与限制。"""

    name: str
    url_pattern: str
    fields: tuple[str, ...]
    priority: int
    notes: str = ""


DATA_SOURCE_MATRIX: dict[str, list[SourceSpec]] = {
    'US': [
        SourceSpec('Google Finance', GF_URL_TEMPLATE, ('price', 'market_cap', 'pe_ratio', 'week52_low', 'week52_high', 'eps', 'beta'), 1),
        SourceSpec('Yahoo Finance', 'https://finance.yahoo.com/quote/{ticker}/key-statistics/', ('forward_pe', 'peg_ratio', 'pb_ratio', 'beta'), 2, '页面可能反爬；优先用 yfinance 程序化读取'),
        SourceSpec('StockAnalysis', 'https://stockanalysis.com/stocks/{ticker}/statistics/', ('enterprise_value', 'ev_ebit', 'roic', 'margins', 'f_score'), 3),
        SourceSpec('MarketBeat', 'https://www.marketbeat.com/stocks/{exchange}/{ticker}/', ('price_target', 'analyst_rating', 'ytd_change_pct'), 4),
        SourceSpec('SEC/company IR', 'company filings / investor relations', ('revenue', 'ebit', 'net_income', 'cash_flow', 'debt', 'equity'), 5),
    ],
    'HK': [
        SourceSpec('Google Finance', GF_URL_TEMPLATE, ('price', 'market_cap', 'pe_ratio', 'week52_low', 'week52_high', 'eps', 'beta'), 1, 'HKG 覆盖不如美股稳定，缺 PB 时走 fallback'),
        SourceSpec('Yahoo Finance', 'https://finance.yahoo.com/quote/{ticker}.HK/key-statistics/', ('forward_pe', 'peg_ratio', 'pb_ratio', 'beta'), 2),
        SourceSpec('MarketScreener', 'https://www.marketscreener.com/search/?q={ticker}', ('price_target', 'consensus', 'enterprise_value', 'pb_ratio'), 3),
        SourceSpec('HKEXnews', 'https://www.hkexnews.hk/search/titlesearch.xhtml?lang=en', ('annual_report', 'interim_report', 'cash_flow', 'debt', 'equity'), 4, '发行人披露为准，PDF/HTML 可由 LLM webfetch 抽表'),
        SourceSpec('Company IR', 'company investor relations', ('revenue', 'ebit', 'net_income', 'capex', 'shares'), 5),
    ],
    'JP': [
        SourceSpec('Google Finance', GF_URL_TEMPLATE, ('price', 'market_cap', 'pe_ratio', 'week52_low', 'week52_high', 'eps', 'beta'), 1),
        SourceSpec('Yahoo Finance', 'https://finance.yahoo.com/quote/{ticker}.T/key-statistics/', ('forward_pe', 'peg_ratio', 'pb_ratio', 'beta'), 2),
        SourceSpec('MarketScreener', 'https://www.marketscreener.com/search/?q={ticker}', ('price_target', 'consensus', 'enterprise_value', 'pb_ratio'), 3),
        SourceSpec('EDINET', 'https://disclosure2.edinet-fsa.go.jp/weee0060.aspx', ('xbrl', 'financial_statements', 'cash_flow', 'debt', 'equity'), 4, '英文 XBRL 仅辅助，日文原文为准'),
        SourceSpec('Company IR', 'company investor relations', ('revenue', 'ebit', 'net_income', 'capex', 'shares'), 5),
    ],
    'KR': [
        SourceSpec('Google Finance', GF_URL_TEMPLATE, ('price', 'market_cap', 'pe_ratio', 'week52_low', 'week52_high', 'eps', 'beta'), 1),
        SourceSpec('Yahoo Finance', 'https://finance.yahoo.com/quote/{ticker}.KS/key-statistics/', ('forward_pe', 'peg_ratio', 'pb_ratio', 'beta'), 2),
        SourceSpec('MarketScreener', 'https://www.marketscreener.com/search/?q={ticker}', ('price_target', 'consensus', 'enterprise_value', 'pb_ratio'), 3),
        SourceSpec('DART/OpenDART', 'https://englishdart.fss.or.kr/mainEng.do', ('xbrl', 'financial_statements', 'cash_flow', 'debt', 'equity'), 4, '英文披露仅辅助，韩文/XBRL 为准'),
        SourceSpec('Company IR', 'company investor relations', ('revenue', 'ebit', 'net_income', 'capex', 'shares'), 5),
    ],
    'CN': [
        SourceSpec('Google Finance', GF_URL_TEMPLATE, ('price', 'market_cap', 'pe_ratio', 'week52_low', 'week52_high', 'eps', 'beta'), 1, 'SHA/SZ A股覆盖不如美股稳定'),
        SourceSpec('yfinance', 'programmatic API', ('forward_pe', 'peg_ratio', 'enterprise_value', 'beta', 'financial_ratios'), 2, '688256.SS 返回完整 info + BS/IS/CF'),
        SourceSpec('MarketScreener', 'https://www.marketscreener.com/search/?q={ticker}', ('price_target', 'consensus', 'enterprise_value', 'pb_ratio'), 3),
        SourceSpec('巨潮资讯/CNInfo', 'https://www.cninfo.com.cn/', ('annual_report', 'interim_report', 'cash_flow', 'debt', 'equity'), 4, '证监会指定信息披露平台'),
        SourceSpec('Company IR', 'cambricon.com investor relations', ('revenue', 'ebit', 'net_income', 'capex', 'shares'), 5),
    ],
    'CRYPTO_BTC': [
        SourceSpec('CoinGecko', 'https://api.coingecko.com/api/v3/coins/{coin_id}', ('price', 'market_cap', 'volume', 'circulating_supply', 'total_supply'), 1),
        SourceSpec('mempool.space', 'https://mempool.space/api/v1/...', ('hash_rate', 'fees', 'mempool', 'network_health'), 2),
        SourceSpec('blockchain.com charts', 'https://api.blockchain.info/charts/{chart}?format=json', ('transactions', 'active_addresses_proxy', 'fees'), 3),
        SourceSpec('LookIntoBitcoin', 'https://www.lookintobitcoin.com/charts/', ('mvrv_z_score', 'nvt', 'cycle_indicators'), 4, '公开图表优先，非稳定 API'),
        SourceSpec('SoSoValue/Farside/CMC ETF', 'public ETF tracker pages', ('spot_etf_aum', 'flows'), 5),
    ],
    'CRYPTO_POS': [
        SourceSpec('CoinGecko', 'https://api.coingecko.com/api/v3/coins/{coin_id}', ('price', 'market_cap', 'volume', 'circulating_supply', 'total_supply'), 1),
        SourceSpec('DeFiLlama', 'https://api.llama.fi/protocol/{slug}', ('tvl', 'chain_tvl'), 2),
        SourceSpec('DeFiLlama fees', 'https://api.llama.fi/overview/fees/{slug}', ('fees', 'revenue', 'holders_revenue'), 3),
        SourceSpec('Chain explorer / staking dashboard', 'chain-specific public pages', ('staking_ratio', 'validators', 'active_addresses'), 4),
        SourceSpec('Company/project docs', 'protocol docs / foundation reports', ('supply_inflation', 'tokenomics'), 5),
    ],
}

# ──────────────────────────────────────────
# Google Finance 文本解析器
# ──────────────────────────────────────────

def parse_google_finance(text: str, market: str) -> dict:
    """将 Google Finance webfetch 文本 → 结构化 dict

    提取字段: price, currency, change_pct, market_cap, pe_ratio,
              week52_high, week52_low, eps, beta, dividend_yield,
              prev_close, open, high, low
    """
    result: dict = {}

    # ── 币种 ──
    cur = CURRENCY_MAP.get(market, {}).get('symbol', '$')
    result['currency'] = CURRENCY_MAP.get(market, {}).get('code', 'USD')
    # escape special chars for regex
    cur_esc = re.escape(cur)

    # ── 价格 ──
    # pattern: after公司名, e.g. "Corp$215.22" or "LtdHK$464.40" or "Corp¥2,870.00" or "Ltd₩285,500.00"
    m = re.search(r'(?:Corp|Inc|Ltd|PLC|Group|Holdings|Co)[\s$]*' + cur_esc + r'([\d,]+\.?\d*)', text)
    if m:
        result['price'] = float(m.group(1).replace(',', ''))

    # ── 涨跌幅 ──
    m = re.search(r'(?:arrow_upward|arrow_downward)\s*([+-][\d.]+%)', text)
    if m:
        result['change_pct'] = m.group(1)

    # ── 前收 ──
    # Usually near price block - after "Today" and before "Open"
    m = re.search(r'Today.*?(?:GMT[^$]*)?(?:·.*?)?' + cur_esc + r'([\d,]+\.?\d*)', text)
    if m and m.group(1):
        prev = float(m.group(1).replace(',', ''))
        if abs(prev - result.get('price', 0)) < result.get('price', 1) * 0.3:
            result['prev_close'] = prev

    # ── 市值 ──
    m = re.search(r'Mkt\.\s*cap\s*([\d.]+)\s*(T|B|M|K)', text)
    if m:
        result['market_cap'] = m.group(1) + m.group(2)

    # ── P/E ──
    m = re.search(r'P/?E\s*ratio\s*([\d,.]+?)(?:52|$)', text)
    if m:
        result['pe_ratio'] = m.group(1)

    # ── 52周高低 ──
    m = re.search(r'52-wk\s*high\s*' + cur_esc + r'?([\d,]+\.?\d*?)52', text)
    if not m:
        m = re.search(r'52-wk\s*high\s*' + cur_esc + r'?([\d,]+\.?\d*)', text)
    if m:
        result['week52_high'] = m.group(1)
    m = re.search(r'52-wk\s*low\s*' + cur_esc + r'?([\d,]+\.?\d*)', text)
    if m:
        result['week52_low'] = m.group(1)

    # ── EPS ──
    m = re.search(r'EPS\s*' + cur_esc + r'?([\d,]+\.?\d*)', text)
    if m:
        result['eps'] = m.group(1)

    # ── Beta ──
    m = re.search(r'Beta\s*([\d.]+)', text)
    if m:
        result['beta'] = m.group(1)

    # ── 股息率 ──
    m = re.search(r'Dividend\s*([\d.]+%)', text)
    if m:
        result['dividend_yield'] = m.group(1)

    # ── 发行股数 ──
    m = re.search(r'Shares\s*outstanding\s*([\d.]+)\s*(T|B|M|K)', text)
    if m:
        result['shares_outstanding'] = m.group(1) + m.group(2)

    return result


def get_market_for_ticker(ticker: str) -> str:
    """返回内部市场代码: US/HK/JP/KR/CRYPTO_BTC/CRYPTO_POS。"""
    if ticker == 'BTC':
        return 'CRYPTO_BTC'
    if ticker in CRYPTO_IDS:
        return 'CRYPTO_POS'
    return STOCK_REGISTRY.get(ticker, ('', '', 'US'))[2]


def build_google_finance_url(ticker: str) -> str:
    """构造跨市场 Google Finance URL。"""
    code, exchange, _market = STOCK_REGISTRY[ticker]
    return GF_URL_TEMPLATE.format(code=code, exchange=EXCHANGE_TO_GF[exchange])


def get_source_chain(ticker: str) -> list[SourceSpec]:
    """返回某标的的数据源 fallback 顺序。"""
    return DATA_SOURCE_MATRIX.get(get_market_for_ticker(ticker), [])


def source_chain_summary(ticker: str) -> str:
    """用于 prompt/日志的简短来源摘要。"""
    chain = get_source_chain(ticker)
    return ' → '.join(source.name for source in sorted(chain, key=lambda s: s.priority))


# ──────────────────────────────────────────
# 加密 API 端点 (CoinGecko + DeFiLlama)
# ──────────────────────────────────────────

COINGECKO_PRICE_API = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_COIN_API = "https://api.coingecko.com/api/v3/coins/{coin_id}"

# 加密资产 → CoinGecko ID
CRYPTO_IDS: dict[str, str] = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'SOL': 'solana',
    'BNB': 'binancecoin',
}

# DeFiLlama 端点
DEFILLAMA_FEES_API = "https://api.llama.fi/overview/fees/{slug}"
DEFILLAMA_TVL_API = "https://api.llama.fi/v2/chains"

# 加密 → DeFiLlama slug
CRYPTO_LLAMA_SLUGS: dict[str, str] = {
    'ETH': 'ethereum',
    'SOL': 'solana',
    'BNB': 'bsc',
}

# PoS 链的 staking explorer API
STAKING_APIS: dict[str, str] = {
    'ETH': 'https://beaconcha.in/api/v1/epoch/latest',
    'SOL': 'https://api.solscan.io/chaininfo?cluster=',
}


def build_coingecko_url(coin_id: str) -> str:
    """CoinGecko 单币行情 URL (免费, 30 cpm)"""
    return f"{COINGECKO_PRICE_API}?ids={coin_id}&vs_currencies=usd&include_market_cap=true&include_24hr_vol=true&include_24hr_change=true"


def build_defillama_fees_url(slug: str) -> str:
    """DeFiLlama fees/revenue (免费开放)"""
    return DEFILLAMA_FEES_API.format(slug=slug)


# ──────────────────────────────────────────
# 辅助：汇率
# ──────────────────────────────────────────

EXCHANGE_RATES: dict[str, float] = {
    'USD': 1.0,
    'HKD': 7.76,
    'JPY': 143.0,
    'KRW': 1340.0,
    'CNY': 7.25,
}


def to_usd(value: float, currency: str) -> float:
    """将本地币种金额转换为 USD"""
    rate = EXCHANGE_RATES.get(currency, 1.0)
    return value / rate


# ──────────────────────────────────────────
# 自检
# ──────────────────────────────────────────

def self_test():
    """打印所有支持的 URL 用于手动验证"""
    print("=== Google Finance URLs ===")
    for ticker, (code, exchange, market) in STOCK_REGISTRY.items():
        gf_ex = EXCHANGE_TO_GF[exchange]
        url = GF_URL_TEMPLATE.format(code=code, exchange=gf_ex)
        print(f"  {ticker:12s} → {url}")

    print("\n=== Crypto URLs ===")
    for ticker, coin_id in CRYPTO_IDS.items():
        print(f"  {ticker:4s} CoinGecko: {build_coingecko_url(coin_id)}")
    for ticker, slug in CRYPTO_LLAMA_SLUGS.items():
        print(f"  {ticker:4s} DeFiLlama: {build_defillama_fees_url(slug)}")


if __name__ == '__main__':
    self_test()
