<div align="center">

# 📊 Stock Analysis

**Multi-market investment analysis framework based on Greenblatt Ranking Methodology**

[![CI](https://github.com/severin/stock-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/severin/stock-analysis/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[English](README.md) · [中文](README-zh.md)

</div>

---

## 🎯 What is this?

Stock Analysis is a **quantitative investment research framework** that ranks assets across multiple markets (US stocks, HK stocks, JP stocks, KR stocks, and crypto) using the proven [Greenblatt Magic Formula](https://en.wikipedia.org/wiki/Magic_formula_investing) enhanced with Piotroski F-Score and PEG ratio.

> **Ranking > Scoring.** We don't ask "Is this a good company?" We ask **"At the current price, is this worth buying?"**

### Key Design Principles

- 🛡️ **Anti-hallucination**: All financial data is fetched in real-time; LLM only writes narrative text with pre-computed numbers
- 🌍 **Multi-market**: Unified ranking across US/HK/JP/KR stocks and crypto assets
- 📐 **Academic-backed**: Greenblatt's EBIT/EV + ROIC ranking, validated by research
- 🔌 **Agent-native**: Designed as an OpenCode plugin with optional direct API fallback

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📈 **Four-Layer Ranking** | L1 EBIT/EV (40%) · L2 ROIC (25%) · L3 F-Score (25%) · L4 PEG (10%) |
| 🌏 **Multi-Market Data** | Yahoo Finance, CoinGecko, DeFiLlama for stocks and crypto |
| 🤖 **LLM-Augmented Reports** | HTML reports with structured sections, charts, and investment verdicts |
| 🔄 **Real-time Ranking** | Auto-generated `index.html` with cross-asset comparison dashboard |
| 🔒 **Anti-Hallucination** | LLM receives pre-computed data; cannot invent financial metrics |
| 🧪 **Well-Tested** | 9 core tests covering data fetch, ranking math, and report validation |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- OpenCode configured with an LLM provider **(recommended)**

### Installation

```bash
git clone https://github.com/severin/stock-analysis.git
cd stock-analysis
pip install -r requirements.txt
```

### Configuration

**If using OpenCode (recommended):**
No extra configuration needed. The tool reads `~/.config/opencode/opencode.jsonc` automatically.

**If running standalone:**
```bash
cp .env.example .env
# Edit .env with your LLM_API_KEY and LLM_BASE_URL
```

### Run Analysis

```bash
# Dry-run: fetch data + compute rankings without LLM
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达 --dry-run

# Full analysis: generates HTML report
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达

# Preview reports
python3 -m http.server 8888
# Open http://localhost:8888/output/index.html
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode Agent (You)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Decides    │  │  Calls      │  │  Reviews            │ │
│  │  which stock│  │  pipeline   │  │  report quality     │ │
│  │  to analyze │  │  --dry-run  │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ injects real data
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Stock Analysis Pipeline (Python)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  fetch/     │  │  ranking/   │  │  reports/           │ │
│  │  yfinance   │  │  greenblatt │  │  engine.py          │ │
│  │  coingecko  │  │  pure math  │  │  jinja2 templates   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  data/      │  │  llm_client │  │  generator.py       │ │
│  │  fetcher.py │  │  (optional  │  │  index.html         │ │
│  │  sources.py │  │   IPC mode) │  │  dashboard          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ writes
                              ▼
                    ┌──────────────────┐
                    │   output/        │
                    │   NVDA_report.html│
                    │   index.html     │
                    └──────────────────┘
```

### Why Two LLM Layers?

| Layer | Role | LLM Usage |
|-------|------|-----------|
| **OpenCode Agent** | Decision-making | Chooses what to analyze, reviews output |
| **Pipeline** | Report generation | Receives pre-computed data, writes narrative only |

The Pipeline's LLM **cannot hallucinate financial data** because all numbers (price, PE, EBIT/EV, ROIC, F-Score) are computed before the LLM sees the prompt.

---

## 📁 Project Structure

```
stock-analysis/
├── src/
│   ├── stock_analysis/          # Core Python package
│   │   ├── cli.py               # CLI entry point
│   │   ├── data/                # Data fetching (yfinance, CoinGecko)
│   │   ├── ranking/             # Greenblatt ranking engine
│   │   ├── reports/             # Report generation (Jinja2)
│   │   ├── registry.py          # Company registry (Single Source of Truth)
│   │   ├── generator.py         # index.html dashboard generator
│   │   └── llm_client.py        # LLM client with OpenCode IPC fallback
│   └── investskill/             # Vendored upstream framework
├── tests/                       # Test suite
├── data/                        # Company metadata
├── output/                      # Generated reports
├── docs/                        # Documentation
├── .opencode/                   # Agent knowledge base
├── .github/workflows/           # CI/CD
├── pyproject.toml               # Package configuration
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # Dev dependencies
├── LICENSE                      # MIT License
└── NOTICE                       # Third-party attributions
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run linting
ruff check src/ --exclude tests

# Run type checking
mypy src/ --exclude tests --ignore-missing-imports

# Run tests
PYTHONPATH="src" pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📊 Methodology: Four-Layer Weighted Ranking v3.0

| Layer | Dimension | Core Metric | Weight | Sort Direction |
|:-----:|-----------|-------------|:------:|----------------|
| **L1** | 💰 Cheap? | **EBIT/EV** | **40%** | High → Low |
| **L2** | 🏭 Profitable? | **ROIC** | **25%** | High → Low |
| **L3** | 🛡️ Safe? | **Piotroski F-Score** | **25%** | High → Low |
| **L4** | 📈 Growth? | **PEG** | **10%** | Low → High |

**Composite Score** = L1_rank × 0.40 + L2_rank × 0.25 + L3_rank × 0.25 + L4_rank × 0.10

Lower composite score = better investment opportunity.

### Crypto Adaptation

- **BTC**: MVRV Z-Score · Hash Rate · On-chain F-Score · Halving cycle
- **PoS (ETH/SOL/BNB)**: MCap/TVL · Staking ratio · Crypto F-Score · Inflation rate

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Setting up your development environment
- Code style guidelines (ruff + mypy)
- Testing requirements
- Git commit conventions

---

## 📄 License

MIT License — see [LICENSE](LICENSE).

Based on [InvestSkill](https://github.com/yennanliu/InvestSkill) v1.6.0 (MIT License, yennanliu) — see [src/investskill/LICENSE](src/investskill/LICENSE).

---

## 🙏 Acknowledgments

- [yfinance](https://github.com/ranaroussi/yfinance) for real-time stock data
- [Jinja2](https://jinja.palletsprojects.com/) for templating
- [Pydantic](https://docs.pydantic.dev/) for data validation
- [LangChain](https://python.langchain.com/) / [LangGraph](https://langchain-ai.github.io/langgraph/) for LLM orchestration
- Joel Greenblatt for the Magic Formula investment methodology
- Joseph Piotroski for the F-Score financial health score