<div align="center">

# 📊 Stock Analysis

**Rank, don't score. Buy the cheapest, not the best.**

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/severin/stock-analysis)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [中文](README-zh.md)

</div>

---

## The Problem

Most investment "AI" tools give you a **score**. 

"NVDA is 8.5/10." "Tesla is 7.2/10."

**This is useless.** A great company at a terrible price is a terrible investment. A mediocre company at a firesale price can make you rich.

Greenblatt proved it in *[The Little Book That Still Beats the Market](https://en.wikipedia.org/wiki/The_Little_Book_That_Beats_the_Market)*: **ranking by EBIT/EV + ROIC outperforms 96% of fund managers.** Not scoring. Not vibes. Pure, cold ranking.

We built the tool we wish existed: **real-time ranking across stocks and crypto, with zero LLM hallucination.**

---

## What It Does

One command. Real data. A ranked list of every asset you track.

```bash
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达
```

Pipeline fetches live prices → computes EBIT/EV, ROIC, F-Score, PEG → ranks everything → generates an HTML report with pre-computed numbers. The LLM only writes narrative. **It cannot hallucinate financial data because it never sees the raw data.**

### Why This Matters

| Other Tools | Stock Analysis |
|-------------|----------------|
| LLM guesses PE ratios from training data | yfinance fetches real PE in real-time |
| "NVDA score: 8.5/10" (meaningless) | "NVDA rank: #3/12 on EBIT/EV" (actionable) |
| One market, one currency | US/HK/JP/KR stocks + BTC/ETH/SOL/BNB, unified ranking |
| Black box scoring | Transparent four-layer formula with academic backing |
| LLM writes everything | LLM only narrates; math is done in Python |

---

## Install

```bash
git clone https://github.com/severin/stock-analysis.git
cd stock-analysis
pip install -r requirements.txt
```

**OpenCode users:** Zero config. Reads your `~/.config/opencode/opencode.jsonc` automatically.  
**Standalone users:** `cp .env.example .env` and add your API key.

---

## Usage

```bash
# Dry-run: fetch + rank, no LLM
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达 --dry-run

# Full report: HTML with charts and narrative
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达

# Regenerate ranking dashboard
PYTHONPATH="src" python3 -m stock_analysis.cli index

# Preview
python3 -m http.server 8888
# http://localhost:8888/output/index.html
```

---

## Features

| | Feature | What It Does |
|---|---------|--------------|
| 📈 | **Four-Layer Ranking** | EBIT/EV (40%) · ROIC (25%) · F-Score (25%) · PEG (10%). Lower composite = better buy. |
| 🌍 | **Multi-Market** | US, HK, JP, KR stocks + crypto. Unified ranking, not siloed. |
| 🔒 | **Anti-Hallucination** | LLM receives pre-computed data blocks. Cannot invent numbers. |
| 🎯 | **Real-Time Data** | yfinance for stocks, CoinGecko/DeFiLlama for crypto. No stale data. |
| 📊 | **HTML Reports** | 8 structured sections, Chart.js visualizations, investment verdict. |
| 🔄 | **Auto Dashboard** | `index.html` auto-regenerates with cross-asset ranking overview. |
| 🤖 | **OpenCode Native** | Plugin mode with IPC fallback. Direct API as default, `--use-opencode-llm` as退化. |

---

## The Ranking Formula

```
Composite = L1_rank × 0.40 + L2_rank × 0.25 + L3_rank × 0.25 + L4_rank × 0.10
```

| Layer | Metric | Weight | Sort |
|:-----:|--------|:------:|------|
| L1 | EBIT/EV (Carlisle's Acquirer's Multiple) | 40% | High → Low |
| L2 | ROIC (Greenblatt's original) | 25% | High → Low |
| L3 | Piotroski F-Score (0-9, safety floor) | 25% | High → Low |
| L4 | Forward PEG (< 1 is cheap) | 10% | Low → High |

**Crypto adaptation:** BTC uses MVRV/Hash Rate/On-chain F-Score/Halving cycle. PoS assets (ETH/SOL/BNB) use MCap/TVL/Staking Ratio/Crypto F-Score/Inflation.

---

## Architecture

```
OpenCode Agent          Pipeline (Python)
     │                         │
     │  "Analyze 英伟达"        │
     └───────────┬─────────────┘
                 │
     ┌───────────▼───────────┐
     │   fetch/ (yfinance)   │
     │   ranking/ (math)     │
     └───────────┬───────────┘
                 │ Pre-computed data
     ┌───────────▼───────────┐
     │   reports/ (Jinja2)   │
     │   LLM narrates only   │
     └───────────┬───────────┘
                 │
              output/
           NVDA_report.html
           index.html
```

Two LLM layers by design:
- **OpenCode Agent**: Decides what to analyze, reviews output quality.
- **Pipeline**: Receives locked data blocks. Writes narrative. Cannot hallucinate.

---

## Project Structure

```
stock-analysis/
├── src/stock_analysis/     # Core package
│   ├── data/               # Fetchers (yfinance, CoinGecko)
│   ├── ranking/            # Greenblatt engine
│   ├── reports/            # Jinja2 templates + validator
│   ├── cli.py              # Entry point
│   └── llm_client.py       # OpenCode IPC or direct API
├── tests/                  # pytest suite
├── data/                   # Company registry JSON
├── output/                 # Generated reports
└── docs/                   # Documentation
```

---

## Development

```bash
pip install -r requirements-dev.txt
ruff check src/
mypy src/ --ignore-missing-imports
PYTHONPATH="src" pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Philosophy

We spent $X on LLM tools that **guessed** financial data. They'd tell us AAPL's PE was 28 when it was 31. They'd rank NVDA "#1" because it's a great company, ignoring that the price already priced in perfection.

**This tool does one thing: tells you what's cheap right now.** Not what's good. Not what will grow. What's cheap.

Greenblatt's formula isn't sexy. It doesn't predict the future. But it beats 96% of fund managers because most investors buy great companies at terrible prices.

Don't be most investors.

---

## License

MIT — see [LICENSE](LICENSE). Based on [InvestSkill](https://github.com/yennanliu/InvestSkill) v1.6.0 (MIT, yennanliu).