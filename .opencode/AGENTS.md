# 股市分析 — Agent 指令

**版本**: 3.0.0 | **更新**: 2026-05-18

## 架构（重构后）

```
股市分析/
├── data/
│   ├── companies.json          ← 26家公司注册表 (Single Source of Truth)
│   └── prices.json             ← yfinance + CoinGecko 缓存
├── src/
│   ├── stock_analysis/         ← 核心引擎 (全部 Python 运行时)
│   │   ├── cli.py              ← 主入口
│   │   ├── data/
│   │   │   ├── fetcher.py      ← yfinance / CoinGecko / DeFiLlama
│   │   │   └── sources.py      ← 数据源矩阵
│   │   ├── ranking/
│   │   │   └── greenblatt.py   ← 四层加权排名 (纯数学, 无 LLM)
│   │   ├── reports/
│   │   │   ├── schema.py       ← Pydantic StockReport
│   │   │   ├── engine.py       ← 报告引擎
│   │   │   ├── config.py       ← LLM 配置 (读取 opencode.jsonc)
│   │   │   └── stages/
│   │   │       ├── scaffold.py ← Stage 0: 脚手架
│   │   │       ├── search.py   ← Stage 1-2: LLM 生成 JSON
│   │   │       ├── render.py   ← Stage 3: Jinja2 → HTML
│   │   │       └── validate.py ← Stage 4: 验证
│   │   ├── registry.py         ← 从 companies.json 派生所有映射
│   │   ├── llm_client.py       ← DeepSeek/OpenAI 客户端
│   │   └── generator.py        ← index.html 生成器
│   └── investskill/            ← 方法论层 (prompts, templates, CSS)
│       ├── prompts/            ← 分析框架 prompt
│       ├── templates/          ← Jinja2 报告模板
│       └── _template.html      ← HTML CSS 主模板
├── tests/                      ← pytest (test_engine, test_pipeline, test_ranker, test_validate_crypto)
├── 分析输出/                    ← 报告输出目录
└── index.html                  ← 排名总览 (自动生成)
```

### Pipeline 执行流程

```
1. scaffold  → 识别公司、初始化 StockReport 壳 (registry.py 查 companies.json)
2. fetch     → yfinance (股票) + CoinGecko/DeFiLlama (加密) → prices.json
3. rank      → 纯 Python 计算四层排名 (greenblatt.py, 无 LLM)
4. LLM       → 注入真实数据 + 预计算排名, LLM 仅生成叙述文本
5. render    → Jinja2 模板 (investskill/templates/) → HTML
6. validate  → 检查 8 sections + verdict + charts 完整性
```

**反幻觉设计**: LLM 从不直接接触原始财务数据。所有数值由 yfinance/公开 API 预计算后注入 prompt，LLM 只写叙述。

## 核心命令

```bash
# 完整分析（fetch → rank → LLM → render → validate）
PYTHONPATH="src" python3 -m stock_analysis.cli <公司中文名>

# Dry-run（fetch + rank，不调用 LLM，验证数据管道）
PYTHONPATH="src" python3 -m stock_analysis.cli <公司中文名> --dry-run

# 重新生成 index.html 排名总览
PYTHONPATH="src" python3 -m stock_analysis.cli index

# 监听分析输出目录，自动重建 index.html
PYTHONPATH="src" python3 -m stock_analysis.cli watch

# 验证 HTML 报告
PYTHONPATH="src" python3 -m stock_analysis.cli validate <报告路径>

# 刷新公开数据（yfinance 股票 + CoinGecko/DeFiLlama 加密，无 AI 依赖）
PYTHONPATH="src" python3 -c "from stock_analysis.data.fetcher import sync_public_data_to_json; sync_public_data_to_json()"

# 本地预览
python3 -m http.server 8888
# http://localhost:8888/index.html
```

### 开发命令

```bash
# 测试 (CI 运行子集)
PYTHONPATH="src" pytest tests/test_engine.py tests/test_pipeline.py tests/test_ranker.py tests/test_validate_crypto.py -v

# Lint
ruff check src/stock_analysis/ --exclude tests

# Type check
mypy src/stock_analysis/ --exclude tests --ignore-missing-imports

# 验证 HTML (程序化)
PYTHONPATH="src" python3 -c "
from stock_analysis.reports.stages.validate import validate_html_file
passed, issues = validate_html_file('<报告路径>')
print('OK' if passed else 'FAIL'); [print(f'  {i}') for i in issues]
"
```

## 公司注册表 (Single Source of Truth)

**`data/companies.json`** 是唯一公司数据源。新增/修改公司只需编辑此文件，`registry.py` 自动派生所有映射（ticker ↔ 中文名、yfinance symbol、市场分组等）。

当前 26 家标的:

| 市场 | 标的 |
|:---|:---|
| 🇺🇸 美股 (8) | 英伟达 NVDA, 苹果 AAPL, 英特尔 INTC, 特斯拉 TSLA, AMD, 美光 MU, 礼来 LLY, 博通 AVGO |
| 🇭🇰 港股 (6) | 小米 1810.HK, 腾讯 0700.HK, 阿里巴巴 9988.HK, 美团 3690.HK, 比亚迪 1211.HK, 智谱 2513.HK |
| 🇯🇵 日股 (3) | 丰田 7203.T, 索尼 6758.T, 软银集团 9984.T |
| 🇰🇷 韩股 (4) | SK海力士 000660.KS, 三星电子 005930.KS, 三星生物制药 207940.KS, 现代汽车 005380.KS |
| 🇨🇳 A股 (1) | 寒武纪 688256.SS |
| ₿ 加密 (4) | 比特币 BTC, 以太坊 ETH, 索拉纳 SOL, BNB |

## 评分体系（四层加权排名 v3.0）

> **核心原则**: 排名优于打分。简单的 EBIT/EV + ROIC + F-Score + PEG 四层加权排名，学术验证比任何主观评分更稳健。

| Layer | 维度 | 主指标 | 权重 | 用法 |
|-------|------|--------|:---:|------|
| **L1** | 💰 便不便宜 | **EBIT/EV**（Carlisle 收购者倍数） | **40%** | 从高到低排名 |
| **L2** | 🏭 赚不赚钱 | **ROIC**（Greenblatt 原始选择） | **25%** | 从高到低排名 |
| **L3** | 🛡️ 会不会崩 | **Piotroski F-Score (0-9)** | **25%** | 安全底线，从高到低排名 |
| **L4** | 📈 增长值不值 | **PEG** (Forward PEG < 1 才划算) | **10%** | 从低到高排名 |

```
综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10
综合排名 = 综合分从小到大排序 (越小越好)
```

PEG 权重 10% 且排在最后——深度价值投资不追求成长性，以避坑和安全边际为主要任务。

### 特殊情况

- **加密货币（BTC）**: L1 MVRV Z-Score（反向映射）, L2 算力+网络强度, L3 改编版 F-Score, L4 减半周期
- **PoS 加密（ETH/SOL/BNB）**: L1 MCap/TVL, L2 Staking 比率, L3 Crypto F-Score(0-6), L4 年通胀率
- **港股/日股/韩股/A股**: 同一公式，币种标注差异，部分字段待完善
- **困境反转**: 统一使用 Non-GAAP Forward Estimate，排名对口径不敏感

### 输出格式（必须）

每次分析必须输出:
- 四层排名表 (`greenblatt_ranking`) + 权重 + 加权分
- Piotroski F-Score 明细卡 (9 项逐项打分)
- 投资信号块 + 综合分 + 综合排名
- HTML 报告: 8 节 (S1-S8) + verdict, CSS 来自 `investskill/_template.html`

## 多市场支持状态

| 市场 | 价格源 | 财务源 | 排名适配 | 状态 |
|:---|:---|:---|:---|:---:|
| 美股 | yfinance (实时) | yfinance BS/IS/CF 自动推算 | 标准四层 | ✅ |
| 港股 | yfinance (1810.HK 等) | yfinance BS/IS/CF | 标准四层 + HKD标注 | 🟡 数据源待完善 |
| 日股 | yfinance (7203.T 等) | yfinance BS/IS/CF | 标准四层 + JPY标注 | 🟡 数据源待完善 |
| 韩股 | yfinance (000660.KS 等) | yfinance BS/IS/CF | 标准四层 + KRW标注 | 🟡 数据源待完善 |
| A股 | yfinance (688256.SS) | yfinance BS/IS/CF | 标准四层 + CNY标注 | 🟡 仅1家试验 |
| 加密 BTC | CoinGecko + yfinance | mempool.space / LookIntoBitcoin | MVRV+算力+F-Score+减半 | ✅ |
| 加密 PoS | CoinGecko + DeFiLlama | 链浏览器 / 官方 staking | MCap/TVL+Staking+CF-Score+通胀 | 🟡 staking/通胀待补强 |

### 🚨 防降级规则（必须遵守）

市场支持状态**只影响数据源选择和缺失字段披露**，**不影响报告生成等级**。用户要求"综合分析/出报告/生成研报"时，港股、日股、韩股、A股和加密资产必须按同一档位生成正式 HTML 报告。不得因为"数据源待完善""非美股"而降级为聊天摘要。

### 数据源优先级

1. **官方披露/公司 IR** (最高优先级)
2. **交易所/XBRL** (EDINET, DART, HKEXnews)
3. **行情层** (yfinance, Google Finance)
4. **二手聚合站** (StockAnalysis, MarketBeat — 仅交叉验证)

## 分析档位（触发词 → 输出）

| 你说 | 出什么 |
|:---|:---|
| "综合分析"/"出报告"/"生成研报" | 1 份 HTML |
| "完整分析"/"出完整研报" | HTML + 3 MD |
| "快速看下"/"估值" | 1 份 01_整体分析.md |
| "收纳以往分析" | 归档旧分析到 `以往分析/` |
| "重算排名" | 只跑 Greenblatt 四层排名 |

## 归档规则

- 公司文件夹 → **中文名**
- 文件命名 → `YYMMDD-NN_分析类型.md`
- 新日期分析 → 旧文件移入 `以往分析/`

## 批量分析执行策略（🚫 禁止并发）

**3+ 家公司同时分析时，必须逐家自行执行，禁止后台并发派发。**

原因: 后台子代理并发槽位仅 1-2 个，多发必饿死。
正确节奏: 搜索→评分→写文件，完成一家再下一家。

## HTML 验证（🚨 每次生成后必须运行）

```bash
PYTHONPATH="src" python3 -m stock_analysis.cli validate <报告路径>
```

验证内容:
- 8 个 section (S1-S8) 存在
- verdict 裁决区存在
- Chart.js 图表存在
- 文件大小 ≥ 15KB
- F-Score 9 项完整 (股票类)
- S7 风险矩阵 ≥ 5 项

验证失败 → 修复 → 重新验证。严禁交付未通过验证的 HTML 报告。

## Git 提交

| 你说 | 执行 |
|:---|:---|
| "帮我提交git" / "提交一下" / "git commit" | 自动执行：查看变更 → 撰写详细提交消息 → 提交 → 推送 |

**规则**:
- 只写详细版（不做选择题），格式统一（二级缩进 `  · `）
- commit message 用中文，前缀遵循约定式提交（`feat:` / `fix:` 等）
- 评分/数据变化标注 `旧值 → 新值`，括号附理由
- 排序固定：项目级变更在前，公司按字母序在后
- 提交后自动 `git push`，不询问

## 关键约束

- **禁止用模型训练数据** — 所有价格/财务数据必须实时搜索或从 yfinance/公开 API 获取
- **排名优于打分** — 禁止 ad-hoc "调整评分"，禁止合成单一总分
- **调输入不调输出** — 改数据来源和计算公式，不改最终呈现
- **百分比优先** — 涨跌用 `+X%`/`-X%`，目标价辅助
- **LLM 仅叙述** — 数学由 Python 完成，LLM 只生成文本叙述

## 历史演进

- v1.0: Greenblatt 原始（EBIT/EV + ROIC）→ 两层
- v2.0: Greenblatt 扩展（EBIT/EV + ROIC + F-Score 验证不参与排名）→ 三层
- v3.0: 四层加权（L1 40% + L2 25% + L3 25% + L4 10%）→ 当前
