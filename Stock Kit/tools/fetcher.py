"""数据采集: marketbeat.com + trefis.com → 结构化数据

混合架构:
  1. Python 层: 从 JSON 缓存读取 (Stock Kit/data/prices.json)
  2. LLM 层: 用 webfetch 工具填充 JSON 缓存
  3. fallback: HTML regex 解析 (marketbeat.com)

返回 PriceSnapshot 字典，传给 ranker 和 LLM prompt。
"""

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / 'data'
PRICES_JSON = DATA_DIR / 'prices.json'


@dataclass
class PriceSnapshot:
    ticker: str
    price: float = 0.0
    currency: str = "$"
    market_cap: str = ""
    enterprise_value: str = ""
    ytd_change_pct: str = ""
    pe_ratio: str = ""
    forward_pe: str = ""
    peg_ratio: str = ""
    week52_low: str = ""
    week52_high: str = ""
    price_target: str = ""
    # 排名指标
    ebit_ev: str = ""
    roic: str = ""
    f_score: int = 0
    fcf_yield: str = ""
    revenue_growth: str = ""
    # 财报数据
    revenue: str = ""
    ebit: str = ""
    net_income: str = ""
    beta: str = ""
    # BTC 专用
    mvrv_z_score: float = 0.0
    hash_rate_eh: float = 0.0
    days_since_halving: int = 0
    source: str = "marketbeat.com"

    @property
    def ebit_ev_num(self) -> Optional[float]:
        try:
            return float(self.ebit_ev.rstrip('%'))
        except (ValueError, AttributeError):
            return None

    @property
    def roic_num(self) -> Optional[float]:
        try:
            return float(self.roic.rstrip('%'))
        except (ValueError, AttributeError):
            return None

    @property
    def peg_num(self) -> Optional[float]:
        try:
            return float(self.peg_ratio.rstrip('x').strip())
        except (ValueError, AttributeError):
            return None


TICKER_MAP: dict[str, str] = {
    '英伟达': 'NVDA',
    '苹果': 'AAPL',
    '特斯拉': 'TSLA',
    '英特尔': 'INTC',
    'AMD': 'AMD',
    '美光': 'MU',
    '小米': '1810.HK',
    '比特币': 'BTC',
}

TICKER_TO_NAME = {v: k for k, v in TICKER_MAP.items()}


def save_prices(snapshots: list[PriceSnapshot]) -> Path:
    """保存到 JSON 缓存 (LLM 侧采集完成后调用)"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for snap in snapshots:
        data[snap.ticker] = asdict(snap)
    PRICES_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return PRICES_JSON


def load_prices() -> dict[str, PriceSnapshot]:
    """从 JSON 缓存加载"""
    if not PRICES_JSON.exists():
        return {}
    raw = json.loads(PRICES_JSON.read_text(encoding='utf-8'))
    result = {}
    for ticker, d in raw.items():
        result[ticker] = PriceSnapshot(**d)
    return result


def fetch_all_8(logger=None) -> dict[str, PriceSnapshot]:
    """主入口: 加载 8 家数据 (从缓存或样例)"""
    data = load_prices()
    log = logger

    if data:
        if log:
            log.info(f"  从缓存加载: {PRICES_JSON} ({len(data)} 家)")
        return data

    if log:
        log.warning("  缓存为空, 使用内置样例数据 (非实时!)")
    return _sample_data()


def _sample_data() -> dict[str, PriceSnapshot]:
    return {
        'NVDA': PriceSnapshot(
            ticker='NVDA',
            price=191.48, market_cap='$4.7T',
            ytd_change_pct='+35.2%', pe_ratio='45.3', forward_pe='41.2',
            peg_ratio='0.66x', week52_low='$110.00', week52_high='$210.00',
            ebit_ev='2.52%', roic='55.5%', f_score=8, fcf_yield='1.8%',
            revenue_growth='+78%',
        ),
        'AAPL': PriceSnapshot(
            ticker='AAPL',
            price=195.50, market_cap='$3.0T',
            ytd_change_pct='+15.6%', pe_ratio='32.5', forward_pe='28.7',
            peg_ratio='2.15x', week52_low='$160.00', week52_high='$260.00',
            ebit_ev='5.8%', roic='48.2%', f_score=7, fcf_yield='3.5%',
            revenue_growth='+5%',
        ),
        'TSLA': PriceSnapshot(
            ticker='TSLA',
            price=212.00, market_cap='$678B',
            ytd_change_pct='+20.3%', pe_ratio='65.2', forward_pe='58.3',
            peg_ratio='3.80x', week52_low='$140.00', week52_high='$490.00',
            ebit_ev='4.1%', roic='22.8%', f_score=6, fcf_yield='1.2%',
            revenue_growth='+8%',
        ),
        'INTC': PriceSnapshot(
            ticker='INTC',
            price=124.82, market_cap='$546B',
            ytd_change_pct='+238%', pe_ratio='0.00', forward_pe='31.5',
            peg_ratio='1.05x', week52_low='$18.97', week52_high='$130.57',
            ebit_ev='1.8%', roic='-4.52%', f_score=4, fcf_yield='-12.5%',
            revenue_growth='+23%',
        ),
        'AMD': PriceSnapshot(
            ticker='AMD',
            price=158.30, market_cap='$256B',
            ytd_change_pct='+12.4%', pe_ratio='68.5', forward_pe='32.1',
            peg_ratio='0.59x', week52_low='$87.00', week52_high='$195.00',
            ebit_ev='1.5%', roic='4.0%', f_score=6, fcf_yield='1.5%',
            revenue_growth='+42%',
        ),
        'MU': PriceSnapshot(
            ticker='MU',
            price=178.40, market_cap='$199B',
            ytd_change_pct='+62.7%', pe_ratio='20.52', forward_pe='10.1',
            peg_ratio='0.12x', week52_low='$64.74', week52_high='$185.00',
            ebit_ev='7.2%', roic='19.5%', f_score=7, fcf_yield='0.5%',
            revenue_growth='+47%',
        ),
        '1810.HK': PriceSnapshot(
            ticker='1810.HK',
            price=58.45, market_cap='$187B HKD', currency='HKD',
            ytd_change_pct='+115%', pe_ratio='58.9', forward_pe='40.5',
            peg_ratio='0.82x', week52_low='$24.75 HKD', week52_high='$64.00 HKD',
            ebit_ev='1.7%', roic='8.5%', f_score=6, fcf_yield='1.0%',
            revenue_growth='+48%',
        ),
        'BTC': PriceSnapshot(
            ticker='BTC',
            price=96378.00, currency='$', market_cap='$1.9T',
            ytd_change_pct='+22.7%', pe_ratio='N/A', forward_pe='N/A',
            peg_ratio='N/A', week52_low='$60,000', week52_high='$110,000',
            ebit_ev='N/A', roic='N/A', f_score=5, fcf_yield='N/A',
            revenue_growth='N/A',
        ),
    }


def parse_marketbeat(html: str, ticker: str) -> Optional[PriceSnapshot]:
    """从 marketbeat.com 页面 HTML 提取关键数据 (fallback)"""
    snap = PriceSnapshot(ticker=ticker, source="marketbeat.com")
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)

    price_matches = re.findall(r'\$?([\d,]+\.?\d*)', html[:2000])
    if price_matches:
        snap.price = float(price_matches[0].replace(',', ''))

    mc = re.search(r'(?:Market Cap|Market Capitalization)[:\s]*\$?([\d,.]+)\s*(trillion|billion|million|T|B|M)?', html, re.DOTALL | re.IGNORECASE)
    if mc:
        val, unit = mc.groups()
        num = float(val.replace(',', ''))
        u = {'trillion': 'T', 'billion': 'B', 'million': 'M', 'T': 'T', 'B': 'B', 'M': 'M'}.get((unit or '').lower(), '')
        snap.market_cap = f"${num:.1f}{u}" if u else f"${num:,.0f}"

    ytd = re.search(r'(?:increased|decreased)\s+by\s+([\d.]+)%', text)
    if ytd:
        direction = '+' if 'increased' in text[ytd.start()-30:ytd.end()] else '-'
        snap.ytd_change_pct = f"{direction}{ytd.group(1)}%"

    yr = re.search(r'52.Week Range.*?\$([\d,.]+)\s*[-–▼▲]+\s*\$([\d,.]+)', text)
    if yr:
        snap.week52_low = f"${yr.group(1)}"
        snap.week52_high = f"${yr.group(2)}"

    fpe = re.search(r'Forward P/?E\s*(?:Ratio)?.*?<strong>([\d,.]+)', html, re.DOTALL)
    if fpe:
        snap.forward_pe = fpe.group(1)

    pe = re.search(r'P/?E\s*(?:Ratio)?.*?<strong>([\d,.]+)', html, re.DOTALL)
    if pe:
        snap.pe_ratio = pe.group(1)

    return snap
