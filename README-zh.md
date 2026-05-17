<div align="center">

# 📊 股市分析 (Stock Analysis)

**排名优于打分。买最便宜的，不是最好的。**

[![CI](https://img.shields.io/badge/CI-passing-brightgreen)](https://github.com/severin/stock-analysis)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) · [中文](README-zh.md)

</div>

---

## 问题

大多数投资"AI"工具给你一个**评分**。

"英伟达 8.5/10"。"特斯拉 7.2/10"。

**这没用。** 一家伟大的公司如果在糟糕的价格买入，就是糟糕的投资。一家平庸的公司如果在跳楼价买入，可以让你暴富。

Greenblatt 在《*[股市稳赚](https://en.wikipedia.org/wiki/The_Little_Book_That_Beats_the_Market)*》中证明了：**按 EBIT/EV + ROIC 排名，跑赢 96% 的基金经理。** 不是打分。不是 vibe。纯粹的、冷酷的排名。

我们做了我们希望存在的工具：**股票和加密的实时排名，零 LLM 幻觉。**

---

## 它做什么

一条命令。真实数据。你跟踪的每个资产的排名列表。

```bash
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达
```

Pipeline 抓取实时价格 → 计算 EBIT/EV、ROIC、F-Score、PEG → 统一排名 → 生成 HTML 报告（数字已预计算）。LLM 只写叙述文本。**它不会幻觉财务数据，因为它从不看原始数据。**

### 为什么这很重要

| 其他工具 | 股市分析 |
|----------|----------|
| LLM 从训练数据猜 PE | yfinance 实时抓取真实 PE |
| "英伟达评分：8.5/10"（无意义） | "英伟达 EBIT/EV 排名：#3/12"（可行动） |
| 单一市场、单一货币 | 美股/港股/日股/韩股 + BTC/ETH/SOL/BNB，统一排名 |
| 黑盒打分 | 透明的四层公式，有学术支撑 |
| LLM 写全部内容 | LLM 只叙述；数学用 Python 算 |

---

## 安装

```bash
git clone https://github.com/severin/stock-analysis.git
cd stock-analysis
pip install -r requirements.txt
```

**OpenCode 用户：** 零配置。自动读取 `~/.config/opencode/opencode.jsonc`。  
**独立运行用户：** `cp .env.example .env` 填入 API 密钥。

---

## 用法

```bash
# Dry-run：抓取 + 排名，不调用 LLM
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达 --dry-run

# 完整报告：含图表和叙述的 HTML
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达

# 重新生成排名看板
PYTHONPATH="src" python3 -m stock_analysis.cli index

# 本地预览
python3 -m http.server 8888
# http://localhost:8888/output/index.html
```

---

## 功能

| | 功能 | 说明 |
|---|---------|------|
| 📈 | **四层加权排名** | EBIT/EV (40%) · ROIC (25%) · F-Score (25%) · PEG (10%)。综合分越低越值得买。 |
| 🌍 | **多市场统一** | 美股、港股、日股、韩股、加密资产。统一排名，不隔离。 |
| 🔒 | **反幻觉设计** | LLM 接收预计算数据块。无法编造数字。 |
| 🎯 | **实时数据** | 股票用 yfinance，加密用 CoinGecko/DeFiLlama。无过期数据。 |
| 📊 | **HTML 报告** | 8 个结构化章节、Chart.js 可视化、投资信号。 |
| 🔄 | **自动看板** | `index.html` 自动生成，支持跨资产排名总览。 |
| 🤖 | **OpenCode 原生** | 插件模式 + IPC 回退。默认直连 API，`--use-opencode-llm` 为退化方案。 |

---

## 排名公式

```
综合分 = L1排名 × 0.40 + L2排名 × 0.25 + L3排名 × 0.25 + L4排名 × 0.10
```

| 层级 | 指标 | 权重 | 排序 |
|:-----:|--------|:------:|------|
| L1 | EBIT/EV (Carlisle 收购者倍数) | 40% | 高 → 低 |
| L2 | ROIC (Greenblatt 原始选择) | 25% | 高 → 低 |
| L3 | Piotroski F-Score (0-9，安全底线) | 25% | 高 → 低 |
| L4 | 远期 PEG (< 1 才划算) | 10% | 低 → 高 |

**加密资产适配：** BTC 用 MVRV/算力/链上 F-Score/减半周期。PoS 资产（ETH/SOL/BNB）用 MCap/TVL/Staking 比率/Crypto F-Score/通胀率。

---

## 架构

```
OpenCode Agent          Pipeline (Python)
     │                         │
     │  "分析 英伟达"           │
     └───────────┬─────────────┘
                 │
     ┌───────────▼───────────┐
     │   data/ (yfinance)    │
     │   ranking/ (数学计算)  │
     └───────────┬───────────┘
                 │ 预计算数据
     ┌───────────▼───────────┐
     │   reports/ (Jinja2)   │
     │   LLM 只负责叙述       │
     └───────────┬───────────┘
                 │
              output/
           英伟达_报告.html
           index.html
```

双层 LLM 设计：
- **OpenCode Agent**：决定分析什么、审查输出质量。
- **Pipeline**：接收锁定数据块。写叙述。无法幻觉。

---

## 项目结构

```
stock-analysis/
├── src/stock_analysis/     # 核心包
│   ├── data/               # 数据采集 (yfinance, CoinGecko)
│   ├── ranking/            # Greenblatt 排名引擎
│   ├── reports/            # Jinja2 模板 + 验证器
│   ├── cli.py              # 入口
│   └── llm_client.py       # OpenCode IPC 或直连 API
├── tests/                  # pytest 测试套件
├── data/                   # 公司注册表 JSON
├── output/                 # 生成报告
└── docs/                   # 文档
```

---

## 开发

```bash
pip install -r requirements-dev.txt
ruff check src/
mypy src/ --ignore-missing-imports
PYTHONPATH="src" pytest tests/ -v
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 哲学

我们在那些**猜**财务数据的 LLM 工具上花了无数钱。它们告诉我们 AAPL 的 PE 是 28，实际是 31。它们把 NVDA 排"#1"因为它是伟大的公司，无视价格已经计入了完美预期。

**这个工具只做一件事：告诉你现在什么便宜。** 不是什么是好的。不是什么会增长。什么是便宜的。

Greenblatt 的公式不性感。它不预测未来。但它跑赢 96% 的基金经理，因为大多数投资者以糟糕的价格买入伟大的公司。

不要做大多数投资者。

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)。基于 [InvestSkill](https://github.com/yennanliu/InvestSkill) v1.6.0 (MIT, yennanliu)。