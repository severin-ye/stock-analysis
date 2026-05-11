"""多市场数据定义: Google Finance URL 模板 + 解析器 + 加密 API

本模块定义:
  1. 各市场 Google Finance URL 模板
  2. 正则解析器 (将 webfetch 返回的文本 → PriceSnapshot 字段)
  3. CoinGecko / DeFiLlama API 端点
  4. 币种汇率映射

用法 (AI agent):
  webfetch(GF_URL['NVDA']['NASDAQ']) → raw_text
  parse_google_finance(raw_text, 'NASDAQ') → dict → 写入 prices.json
"""

import re
import json
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

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
}

# 股票 → (GF code, exchange, market)
STOCK_REGISTRY: dict[str, tuple[str, str, str]] = {
    # 美股
    'NVDA': ('NVDA', 'NASDAQ', 'US'),
    'AAPL': ('AAPL', 'NASDAQ', 'US'),
    'TSLA': ('TSLA', 'NASDAQ', 'US'),
    'INTC': ('INTC', 'NASDAQ', 'US'),
    'AMD': ('AMD', 'NASDAQ', 'US'),
    'MU': ('MU', 'NASDAQ', 'US'),
    # 港股
    '0700.HK': ('0700', 'HKEX', 'HK'),
    '9988.HK': ('9988', 'HKEX', 'HK'),
    '3690.HK': ('3690', 'HKEX', 'HK'),
    '1211.HK': ('1211', 'HKEX', 'HK'),
    # 日股
    '7203.T': ('7203', 'TSE', 'JP'),
    '6758.T': ('6758', 'TSE', 'JP'),
    '9984.T': ('9984', 'TSE', 'JP'),
    # 韩股
    '005930.KS': ('005930', 'KOSPI', 'KR'),
}

# 币种 → 符号/代码
CURRENCY_MAP: dict[str, dict[str, str]] = {
    'US': {'symbol': '$', 'code': 'USD'},
    'HK': {'symbol': 'HK$', 'code': 'HKD'},
    'JP': {'symbol': '¥', 'code': 'JPY'},
    'KR': {'symbol': '₩', 'code': 'KRW'},
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
    'HKD': 7.76,   # 1 USD ≈ 7.76 HKD (pegged)
    'JPY': 143.0,  # approximate
    'KRW': 1340.0, # approximate
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
