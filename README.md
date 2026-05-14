# 📊 综合投资分析报告

基于 **Greenblatt 排名法** 的多市场深度投资分析系统：以美股为主，兼容港股、日股、韩股和加密资产。

> 排名不是对公司优劣的判断，而是对 **"当前价格下值不值得买"** 的量化回答。

---

## 界面预览

### 排名总览页

![投资标的综合排名总览](assets/readme/ranking-overview.png)

首页聚合展示全部标的的综合排名、分市场分组和横向对比图，适合先看谁在当前价格下更值得继续深挖。

### 个股报告页

![苹果综合分析报告示例](assets/readme/apple-report.png)

单页报告采用 8 个结构化章节，集中呈现估值、过去一年走势、护城河、风险分析和最终投资信号。



## 方法论：四层加权排名体系 v3.0

我们的核心理念是 **排名优于打分**。采用经典的 Greenblatt 魔法公式，并结合 Piotroski F-Score 和 PEG 估值，构建了四层加权排名体系：

| 层级 | 维度 | 核心指标 | 权重 | 排序逻辑 |
|:----:|------|----------|:----:|----------|
| **L1** | 💰 便不便宜 | **EBIT/EV**（企业收益率） | **40%** | 越高越好 |
| **L2** | 🏭 赚不赚钱 | **ROIC**（投入资本回报率） | **25%** | 越高越好 |
| **L3** | 🛡️ 会不会崩 | **Piotroski F-Score**（0-9） | **25%** | 越高越安全 |
| **L4** | 📈 增长值不值 | **PEG**（市盈增长比率） | **10%** | 越低越好 |

### 综合推荐公式

```
综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10
综合排名 = 综合分从小到大排序（分数越低，排名越靠前）
```

> **为什么 PEG 只占 10%？** 深度价值投资不以成长率为核心驱动。安全边际和基本面健康度才是首要考量。

### 模型演进

- **v1.0** — Greenblatt 原始公式：EBIT/EV + ROIC（两层）
- **v2.0** — 加入 F-Score 作为安全验证（三层）
- **v3.0** — 四层加权合成，PEG 纳入但权重最低（当前版本）

---

## 如何使用

### 本地预览

```bash
cd /home/severin/Codelib/股市分析
python3 -m http.server 8888
```

打开浏览器访问：http://localhost:8888/index.html

### 自动监听并重建首页

```bash
cd /home/severin/Codelib/股市分析
source .venv/bin/activate
PYTHONPATH="Stock Kit" python3 -m tools.pipeline watch
```

该命令会轮询监听 分析输出 下的 HTML 报告新增、修改、删除和重命名；一旦检测到变化，就自动重建 index.html。

### 数据来源

所有数据均来自实时搜索，经至少两个来源交叉验证后方可使用：

| 数据源 | 提供数据 |
|--------|----------|
| Google Finance / yfinance | 美股、港股、日股、韩股股价、PE、市值、52周高低、EPS、Beta |
| StockAnalysis / MarketBeat | 美股 EV/EBIT、ROIC、Forward PEG、目标价、F-Score 交叉验证 |
| Yahoo Finance / MarketScreener | 港股、日股、韩股 PB、Forward PE、目标价、共识、估值交叉验证 |
| HKEXnews / EDINET / DART | 港股、日股、韩股官方财报、XBRL、现金流、负债、股本 |
| 公司 IR | 所有市场的年报、季报、财报电话会、产能和业务数据 |
| CoinGecko API | 加密货币价格、市值、成交量、供给 |
| DeFiLlama API | 加密 TVL、Fees、Revenue |
| mempool.space / blockchain.com | BTC 网络健康、交易、费用、算力辅助 |
| LookIntoBitcoin / SoSoValue / Farside | BTC MVRV/NVT/周期、ETF AUM/flows |
| beaconcha.in / Solscan / BscScan | ETH/SOL/BNB staking、验证者、地址活跃度 |

跨市场原则：数据源状态只影响字段来源和缺失披露，不影响报告生成档位；非美股不得降级为聊天摘要。

---

## 目录结构

```
股市分析/
├── README.md                 ← 你正在读的文件
├── index.html                ← 导航首页（本地预览入口）
├── AGENTS.md                 ← AI Agent 内部知识库
├── assets/
│   └── readme/               ← README 截图资源
├── Stock Kit/
│   ├── InvestSkill/          ← 分析框架核心（只保留 prompt、模板、文档等静态资产）
│   └── tools/                ← 全部 Python 运行时代码与测试
│       ├── pipeline.py
│       ├── runtime/
│       │   └── report_engine/
│       └── tests/
├── 分析输出/                 ← 所有公司与资产的 HTML 报告
└── .sisyphus/                ← 会话数据（自动生成）
```

---

## 输出格式

每家公司/标的的分析报告包含以下内容：

- **涨跌总览表** — 五维对比（涨跌比例 / 对应价格 / 概率权重 / 行业对比）
- **四层排名表** — 各层指标数值、排名、投资判断
- **Piotroski F-Score 明细卡** — 9 项财务健康指标逐项打分
- **投资信号块** — 综合推荐等级与关键信号提示

HTML 报告包含 8 个结构化章节（S1-S8），最终输出投资建议（Verdict）。

---

## 特殊标的处理

| 标的 | 适配方式 |
|------|----------|
| **比特币（BTC）** | L1 改用 MVRV Z-Score，L2 改用算力+网络强度，L3 使用链上改编版 F-Score，L4 参考减半周期位置 |
| **港股（小米）** | 同一排名公式，标注跨市场估值差异 |
| **困境反转股** | 使用 Non-GAAP Forward Estimate 计算 EBIT/EV 和 ROIC |

---

## 技术栈

- **分析框架**：[InvestSkill](https://github.com/yennanliu/invest-skill) v1.6.0（MIT License）
- **报告渲染**：Chart.js 交互式 HTML 报告
- **验证机制**：Python HTML 校验脚本（防 LLM 输出丢失）
- **AI 驱动**：基于 LLM 的实时数据采集与结构化分析

---

## 注意事项

⚠️ **免责声明** — 本分析报告仅供参考，不构成任何投资建议。所有数据基于公开信息和模型分析，存在时效性和误差可能。投资有风险，决策需谨慎。

⚠️ **数据时效性** — 所有股价和市场数据均为分析时点的实时数据，不会自动更新。如需最新判断，请重新运行分析。

---

*最后更新：2026-05-11*
