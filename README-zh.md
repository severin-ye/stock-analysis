<div align="center">

# 📊 股市分析 (Stock Analysis)

**基于 Greenblatt 排名法的多市场量化投资研究框架**

[![CI](https://github.com/severin/stock-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/severin/stock-analysis/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

[English](README.md) · [中文](README-zh.md)

</div>

---

## 🎯 项目简介

**股市分析** 是一个**量化投资研究框架**，采用经过学术验证的 [Greenblatt 魔法公式](https://en.wikipedia.org/wiki/Magic_formula_investing)，结合 Piotroski F-Score 和 PEG 估值指标，对美股、港股、日股、韩股和加密资产进行统一排名。

> **排名优于打分。** 我们不问"这是不是好公司"，而是问 **"在当前价格下，值不值得买？"**

### 核心设计理念

- 🛡️ **反幻觉设计**：所有财务数据实时抓取，LLM 只负责用预计算的数字撰写叙述文本
- 🌍 **多市场统一排名**：美股/港股/日股/韩股/加密资产在同一排名体系内比较
- 📐 **学术验证**：Greenblatt EBIT/EV + ROIC 双层排名，研究证实优于主观评分
- 🔌 **Agent 原生**：为 OpenCode 插件设计，同时支持独立运行和直接 API 调用

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 📈 **四层加权排名** | L1 EBIT/EV (40%) · L2 ROIC (25%) · L3 F-Score (25%) · L4 PEG (10%) |
| 🌏 **多市场数据源** | Yahoo Finance、CoinGecko、DeFiLlama，覆盖股票和加密资产 |
| 🤖 **LLM 增强报告** | 结构化 HTML 报告，含 8 个章节、交互图表和投资信号 |
| 🔄 **实时排名总览** | 自动生成 `index.html` 排名看板，支持跨资产横向对比 |
| 🔒 **数据真实性保障** | LLM 接收预计算数据，无法编造财务指标 |
| 🧪 **完善的测试** | 9 项核心测试覆盖数据采集、排名计算和报告验证 |

---

## 🚀 快速开始

### 前置要求

- Python 3.12+
- 已配置 OpenCode 的 LLM 提供商 **（推荐）**

### 安装

```bash
git clone https://github.com/severin/stock-analysis.git
cd stock-analysis
pip install -r requirements.txt
```

### 配置

**如果使用 OpenCode（推荐）：**
无需额外配置。工具自动读取 `~/.config/opencode/opencode.jsonc`。

**如果独立运行：**
```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 和 LLM_BASE_URL
```

### 运行分析

```bash
# Dry-run：抓取数据 + 计算排名，不调用 LLM
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达 --dry-run

# 完整分析：生成 HTML 报告
PYTHONPATH="src" python3 -m stock_analysis.cli 英伟达

# 预览报告
python3 -m http.server 8888
# 打开 http://localhost:8888/output/index.html
```

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCode Agent (决策层)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  决定分析   │  │  调用       │  │  审查               │ │
│  │  哪家公司   │  │  pipeline   │  │  报告质量           │ │
│  │             │  │  --dry-run  │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ 注入真实数据
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Stock Analysis Pipeline (执行层)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  data/      │  │  ranking/   │  │  reports/           │ │
│  │  yfinance   │  │  greenblatt │  │  engine.py          │ │
│  │  coingecko  │  │  纯数学计算 │  │  Jinja2 模板        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  数据源     │  │  llm_client │  │  generator.py       │ │
│  │  fetcher.py │  │  (可选 IPC  │  │  index.html 看板    │ │
│  │  sources.py │  │   模式)     │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │ 写入
                              ▼
                    ┌──────────────────┐
                    │   output/        │
                    │   英伟达/        │
                    │   index.html     │
                    └──────────────────┘
```

### 为什么需要两层 LLM？

| 层级 | 角色 | LLM 用途 |
|------|------|----------|
| **OpenCode Agent** | 决策层 | 决定分析哪家公司、审查输出质量 |
| **Pipeline** | 执行层 | 接收预计算数据，只撰写叙述文本 |

Pipeline 中的 LLM **无法编造财务数据**，因为所有数字（价格、PE、EBIT/EV、ROIC、F-Score）都在 LLM 看到 prompt 之前已经计算完成。

---

## 📁 项目结构

```
stock-analysis/
├── src/
│   ├── stock_analysis/          # Python 核心包
│   │   ├── cli.py               # 命令行入口
│   │   ├── data/                # 数据采集 (yfinance, CoinGecko)
│   │   ├── ranking/             # Greenblatt 排名引擎
│   │   ├── reports/             # 报告生成 (Jinja2)
│   │   ├── registry.py          # 公司注册表 (单一真相源)
│   │   ├── generator.py         # index.html 看板生成器
│   │   └── llm_client.py        # LLM 客户端 (支持 OpenCode IPC)
│   └── investskill/             # 上游框架 (vendored)
├── tests/                       # 测试套件
├── data/                        # 公司元数据
├── output/                      # 生成报告
├── docs/                        # 文档
├── .opencode/                   # Agent 知识库
├── .github/workflows/           # CI/CD
├── pyproject.toml               # 包配置
├── requirements.txt             # 运行时依赖
├── requirements-dev.txt         # 开发依赖
├── LICENSE                      # MIT 许可证
└── NOTICE                       # 第三方归属声明
```

---

## 🧪 开发

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 运行代码检查
ruff check src/ --exclude tests

# 运行类型检查
mypy src/ --exclude tests --ignore-missing-imports

# 运行测试
PYTHONPATH="src" pytest tests/ -v
```

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 📊 方法论：四层加权排名 v3.0

| 层级 | 维度 | 核心指标 | 权重 | 排序方向 |
|:-----:|------|-------------|:------:|----------------|
| **L1** | 💰 便不便宜 | **EBIT/EV** | **40%** | 高 → 低 |
| **L2** | 🏭 赚不赚钱 | **ROIC** | **25%** | 高 → 低 |
| **L3** | 🛡️ 会不会崩 | **Piotroski F-Score** | **25%** | 高 → 低 |
| **L4** | 📈 增长值不值 | **PEG** | **10%** | 低 → 高 |

**综合分** = L1 排名 × 0.40 + L2 排名 × 0.25 + L3 排名 × 0.25 + L4 排名 × 0.10

综合分越低 = 越值得投资。

### 加密资产适配

- **BTC**: MVRV Z-Score · 算力 · 链上 F-Score · 减半周期
- **PoS (ETH/SOL/BNB)**: MCap/TVL · Staking 比率 · Crypto F-Score · 通胀率

---

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解：
- 开发环境搭建
- 代码风格规范 (ruff + mypy)
- 测试要求
- Git 提交规范

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)。

基于 [InvestSkill](https://github.com/yennanliu/InvestSkill) v1.6.0 (MIT License, yennanliu) — 详见 [src/investskill/LICENSE](src/investskill/LICENSE)。

---

## 🙏 致谢

- [yfinance](https://github.com/ranaroussi/yfinance) 实时股票数据
- [Jinja2](https://jinja.palletsprojects.com/) 模板引擎
- [Pydantic](https://docs.pydantic.dev/) 数据验证
- [LangChain](https://python.langchain.com/) / [LangGraph](https://langchain-ai.github.io/langgraph/) LLM 编排
- Joel Greenblatt — 魔法公式投资方法论
- Joseph Piotroski — F-Score 财务健康评分