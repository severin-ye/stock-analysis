#!/usr/bin/env python3
"""Greenblatt 排名法：读取当前所有 01_整体分析.md，实时计算排名。

用法：
    python3 rank.py              # 输出完整排名表
    python3 rank.py --brief      # 仅输出排名摘要
    python3 rank.py AAPL NVDA    # 仅对比指定公司
"""

import re
import os
import sys
from pathlib import Path

PROJECT_DIR = Path("/home/severin/Codelib/股市分析")

STOCKS = {
    "NVDA":  "英伟达",
    "AAPL":  "苹果",
    "MU":    "美光",
    "TSLA":  "特斯拉",
    "AMD":   "AMD",
    "INTC":  "英特尔",
}

CROSS_MARKET = {
    "1810.HK": "小米",
    "BTC":     "比特币",
}


def parse_md(filepath):
    try:
        text = filepath.read_text()
    except FileNotFoundError:
        return None

    result = {"ticker": None, "name": None, "ebit_ev": None, "roic": None, "fscore": None}

    m = re.search(r'EBIT/EV.*?\|\s*([\d.]+)%', text)
    if m:
        result["ebit_ev"] = float(m.group(1))

    m = re.search(r'ROIC.*?\|\s*[><~]*\s*([\d.]+)%', text)
    if m:
        result["roic"] = float(m.group(1))

    m = re.search(r'ROCE.*?\|\s*([\d.]+)%', text)
    if m:
        result["roic"] = float(m.group(1))

    m = re.search(r'F-Score[：:]\s*[~]*\s*(\d+(?:[.-]\d+)?)', text)
    if m:
        result["fscore"] = m.group(1)

    m = re.search(r'MVRV Z-Score[：:]?\s*([\d.]+)', text)
    if m:
        result["mvrv"] = float(m.group(1))

    for ticker, name in {**STOCKS, **CROSS_MARKET}.items():
        if name in str(filepath):
            result["ticker"] = ticker
            result["name"] = name
            break

    return result


def rank_stocks(data_list):
    us = [d for d in data_list if d and d["ticker"] in STOCKS and d["ebit_ev"] is not None and d["roic"] is not None]

    us.sort(key=lambda d: d["ebit_ev"], reverse=True)
    for i, d in enumerate(us):
        d["l1_rank"] = i + 1

    us.sort(key=lambda d: d["roic"], reverse=True)
    for i, d in enumerate(us):
        d["l2_rank"] = i + 1

    for d in us:
        d["rank_sum"] = d["l1_rank"] + d["l2_rank"]

    us.sort(key=lambda d: d["rank_sum"])
    return us


def print_full(us_stocks, all_data):
    print()
    print("═══ Greenblatt 实时排名 ═══")
    print(f"  L1 = EBIT/EV (越高越便宜)  |  L2 = ROIC (越高越赚钱)")
    print(f"  综合 = L1 + L2 排名和 (越小越值得买)  |  F-Score 独立验证")
    print()
    print(f"{'':4s} {'公司':8s} {'EBIT/EV':>8s} {'L1':>4s} {'ROIC':>8s} {'L2':>4s} {'Sum':>4s} {'F-Score':>8s} {'信号':s}")
    print("-" * 70)

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for d in us_stocks:
        medal = medals.get(d["rank_sum"], "").ljust(2) if d["rank_sum"] <= max([x["rank_sum"] for x in us_stocks] or [0]) else ""
        sig = "BUY" if d["rank_sum"] <= 4 else ("HOLD" if d["rank_sum"] <= 7 else "AVOID")
        print(f"  {medal} {d['name']:6s} {d['ebit_ev']:>7.2f}% {'#' + str(d['l1_rank']):>4s} {d['roic']:>7.1f}% {'#' + str(d['l2_rank']):>4s} {d['rank_sum']:>4d} {d.get('fscore', 'N/A'):>8s} {sig}")

    print()
    print("─" * 70)
    print("  ⛓️ 跨市场（不参与美股排名）：")
    for d in all_data:
        if d and d["ticker"] in CROSS_MARKET:
            if d["ticker"] == "BTC":
                print(f"  BTC  比特币    MVRV Z-Score: {d.get('mvrv', 'N/A')}    改编 F-Score: {d.get('fscore', 'N/A')}/9")
            else:
                print(f"  {d['ticker']:8s} {d['name']:4s}  EBIT/EV: {d.get('ebit_ev', 'N/A')}%    ROCE: {d.get('roic', 'N/A')}%    F-Score: {d.get('fscore', 'N/A')}/9")
    print()


def main():
    brief = "--brief" in sys.argv
    tickers = [a.upper() for a in sys.argv[1:] if not a.startswith("--")]

    all_data = []
    for ticker, name in {**STOCKS, **CROSS_MARKET}.items():
        if tickers and ticker not in tickers:
            continue
        pattern = f"{name}/2*-01_整体分析.md"
        files = sorted(PROJECT_DIR.glob(pattern), reverse=True)
        if files:
            data = parse_md(files[0])
            if data:
                all_data.append(data)

    us_stocks = rank_stocks([d for d in all_data if d and d["ticker"] in STOCKS])

    if brief:
        for d in us_stocks:
            print(f"#{d['l1_rank']+d['l2_rank']} {d['name']}({d['ticker']}) L1#{d['l1_rank']}+L2#{d['l2_rank']}={d['rank_sum']} F-Score:{d.get('fscore','N/A')}")
    else:
        print_full(us_stocks, all_data)


if __name__ == "__main__":
    main()
