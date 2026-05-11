# 股市分析 — 项目知识库

**生成**: 2026-05-10 | **分支**: main

## 概述

美股 + 加密资产综合投资分析项目。基于 InvestSkill v1.6.0（yennanliu，MIT）框架，按 Greenblatt 排名法（EBIT/EV + ROIC + F-Score），输出 Markdown 分析 + Chart.js 交互 HTML 报告。

## 目录结构

```
股市分析/
├── AGENTS.md              ← 本文件
├── index.html             ← 排名总览页（自动生成，由 tools/index_generator.py 驱动）
├── Stock Kit/              ← 核心引擎（Skill + Tool 分离）
│   ├── InvestSkill/        ← 方法论层（prompts、CSS、Jinja2 模板）
│   │   ├── _template.html  ← HTML 报告 CSS 主模板
│   │   ├── prompts/        ← 20个分析框架（stock-eval, dcf-valuation...）
│   │   ├── templates/      ← Jinja2 报告模板 (report.jinja2)
│   │   └── report_engine/  ← LangGraph 流水线 (schema/stages/pipeline)
│   ├── tools/              ← 实现层（数据采集、排名、渲染、验证）
│   │   ├── fetcher.py      ← marketbeat/trefis 数据采集 + JSON 缓存
│   │   ├── ranker.py       ← 纯数学四层加权排名 (无 LLM)
│   │   ├── renderer.py     ← Jinja2 → HTML 渲染
│   │   ├── validator.py    ← HTML 完整性验证
│   │   └── pipeline.py     ← 编排器 (fetch→rank→LLM→render→validate)
│   └── data/               ← 缓存数据
│       └── prices.json     ← 8 家标的实时价格缓存 (LLM 用 webfetch 填充)
├── 分析输出/               ← 所有公司分析报告
│   └── 英伟达/ 苹果/ 特斯拉/ ... ← 报告输出目录
└── .sisyphus/              ← 会话数据 + 日志
```

### Skill ↔ Tool 联动

```
Skill (InvestSkill)         Tool (tools/)
├── 指定 marketbeat 数据源 → fetcher.py 按此抓取
├── 定义四层加权公式      → ranker.py 纯数学实现
├── 提供 Jinja2 模板      → renderer.py 渲染用
└── 指定 8-sections 格式  → validator.py 验证
```

### Pipeline 执行流程

```
1. scaffold → 识别公司、初始化 StockReport 壳
2. fetch    → 读 Stock Kit/data/prices.json (LLM 用 webfetch 填充)
3. rank     → 纯 Python 计算四层排名 (无 LLM, 不幻觉)
4. LLM      → 注入真实数据 + 预计算排名, LLM 仅生成叙述文本
5. render   → Jinja2 模板渲染 HTML
6. validate → 检查 8 sections + verdict + charts 完整性
```

## 分析档位（触发词 → 输出）

| 你说 | 出什么 |
|---|---|
| "综合分析"/"出报告"/"生成研报" | 1 份 HTML |
| "完整分析"/"出完整研报" | HTML + 3 MD |
| "快速看下"/"估值" | 1 份 01_整体分析.md |
| "收纳以往分析" | 归档旧分析到 `以往分析/` |
| "重算排名" | 只跑 Greenblatt 三层排名 |

## 核心规则（每次分析必须遵守）

### 数据采集：Google Finance 优先（多市场统一）

**第一层 — Google Finance（价格/PE/市值/52周高低）**：
| 市场 | Google Finance URL | 能拿到 |
|:---|:---|:---|
| 美股 | `https://www.google.com/finance/quote/{SYMBOL}:NASDAQ` | 股价、PE、市值、52周、EPS、Beta、股息率 |
| 港股 | `https://www.google.com/finance/quote/{CODE}:HKG` | 同上（HKD 计价） |
| 日股 | `https://www.google.com/finance/quote/{CODE}:TYO` | 同上（JPY 计价） |
| 韩股 | `https://www.google.com/finance/quote/{CODE}:KRX` | 同上（KRW 计价） |

**第二层 — 专业源补充（Google 没有的）**：
- EBIT/EV、ROIC、F-Score、PEG → stockanalysis.com + marketbeat.com（美股）/ HKEXnews解析（港股）/ EDINET XBRL（日股）/ DART XBRL（韩股）

**第三层 — 加密专属（Google 不支持）**：
- 价格/市值 → CoinGecko 免费 API
- TVL/Fees/Revenue → DeFiLlama 免费 API
- MVRV Z-Score → LLM webfetch 公开图表提取

参见 `Stock Kit/tools/market_data.py` 解析器和 URL 模板。

### 输出格式
- **百分比优先**：涨跌用 `+X%`/`-X%`，目标价辅助
- **涨跌总览表**：固定5列 `维度|涨跌比例|对应价格|概率权重|行业对比`
- **三层排名表**：固定格式 `Layer|维度|主指标|数值|排名|判断`
- **Piotroski F-Score 明细卡**：9 项逐项打分
- **HTML 报告**：8节（S1-S8+verdict），CSS 来自 `InvestSkill/_template.html`，评分区块替换为三层排名+F-Score卡
- **HTML 验证（🚨 必须）**：每次生成/修改 HTML 报告后，**必须**运行验证：
  ```bash
  PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -c "
from tools.validator import validate_html_file
passed, issues = validate_html_file('<报告路径>')
print('OK' if passed else 'FAIL'); [print(f'  {i}') for i in issues]
"
  ```
  验证失败 → 检查缺失 sections → 修复后重新验证。严禁交付未通过验证的 HTML 报告。

### 多市场支持状态

| 市场 | 价格源 | 财务源 | 排名适配 | 状态 |
|:---|:---|:---|:---|:---:|
| 美股 | Google Finance | stockanalysis + marketbeat | 标准四层 | ✅ |
| 港股 | Google Finance (HKG) | HKEXnews 年报解析 | 标准四层 + HKD标注 | 🟡 数据源待完善 |
| 日股 | Google Finance (TYO) | EDINET XBRL 解析 | 标准四层 + JPY标注 | 🔜 Phase 2 |
| 韩股 | Google Finance (KRX) | DART XBRL 解析 | 标准四层 + KRW标注 | 🔜 Phase 2 |
| 加密 BTC | CoinGecko + webfetch | 公开图表(LookIntoBitcoin) | MVRV+算力+F-Score+减半 | ✅ |
| 加密 PoS | CoinGecko + DeFiLlama | 免费 API | MCap/TVL+Staking+CF-Score+通胀 | 🟡 数据源待采集 |

**加密排名双轨**：
- BTC：L1 MVRV Z-Score · L2 算力 · L3 链上 F-Score · L4 减半周期
- ETH/SOL/BNB (PoS)：L1 MCap/TVL · L2 Staking比率 · L3 Crypto F-Score(0-6) · L4 年通胀率

### 批量分析执行策略（🚫 禁止并发派发）
- **3+ 家公司同时分析时，必须逐家自行执行，禁止 `task(background=true)` 并发派发**
- 原因：后台子代理并发槽位仅 1-2 个，多发必饿死
- 正确节奏：搜索→评分→写文件，完成一家再下一家
- 详见 invest-skill SKILL.md "批量分析执行策略" 章节

### 归档
- 公司文件夹→中文名
- 文件命名→`YYMMDD-NN_分析类型.md`
- 新日期分析→旧文件移入 `以往分析/`

## Git 提交（触发词 → 自动执行）

| 你说 | 执行 |
|---|---|
| "帮我提交git" / "提交一下" / "git commit" | 自动执行：查看变更 → 撰写详细提交消息 → 提交 → 推送 |

**工作流详见**: `InvestSkill/prompts/git-commit.md`

**关键规则**：
- 只写详细版（不做选择题），格式死板统一（二级缩进 `  · `）
- commit message 用中文，前缀遵循约定式提交（`feat:` / `fix:` 等）
- 评分/数据变化标注 `旧值 → 新值`，括号附理由
- 排序固定：项目级变更在前，公司按字母序在后
- 提交后自动 `git push`，不询问

## 命令

```bash
# 启动本地预览
cd /home/severin/Codelib/股市分析 && python3 -m http.server 8888
# 访问 http://localhost:8888/index.html

# 运行分析 Pipeline (dry-run 预览, 不调用 LLM)
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -m tools.pipeline 英伟达 --dry-run

# 运行分析 Pipeline (完整, 调用 LLM)
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -m tools.pipeline 英伟达

# 刷新价格数据 (yfinance 全市场, 无 AI 依赖)
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -c "from tools.fetcher import sync_yfinance_to_json; sync_yfinance_to_json()"

# 重新生成 index.html 排名总览（所有报告生成后必须执行）
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -m tools.pipeline index

# HTML 验证
python3 -m tools.pipeline validate <报告路径>

# Git
cd /home/severin/Codelib/股市分析 && git push origin main

# 运行 InvestSkill 测试 (Node.js, upstream)
cd "Stock Kit/InvestSkill" && npm test

# 运行 Python 验证 (本项目的核心测试)
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -m tools.pipeline validate <报告路径>
PYTHONPATH="Stock Kit:Stock Kit/InvestSkill" python3 -c "
from report_engine.stages.validate import validate_html_file
passed, issues = validate_html_file('<报告路径>')
print('OK' if passed else 'FAIL'); [print(f'  {i}') for i in issues]
"
```

## 评分体系（四层加权排名 v3.0）

> **核心原则**：排名优于打分。简单的 EBIT/EV + ROIC + F-Score + PEG 四层加权排名相加，F-Score 权重比 PEG 高，学术验证比任何主观加权评分更稳健。

### 四层排名（加权合成综合分）

| Layer | 维度 | 主指标 | 权重 | 用法 |
|-------|------|--------|:---:|------|
| **L1** | 💰 便不便宜 | **EBIT/EV**（Carlisle 收购者倍数） | **40%** | 从高到低排名 |
| **L2** | 🏭 赚不赚钱 | **ROIC**（Greenblatt 原始选择） | **25%** | 从高到低排名 |
| **L3** | 🛡️ 会不会崩 | **Piotroski F-Score (0-9)** | **25%** | 安全底线(避坑)，从高到低排名 |
| **L4** | 📈 增长值不值 | **PEG** (Forward PEG < 1 才划算) | **10%** | 从低到高排名 (PEG 越低越好) |

### 综合推荐公式

```
综合分 = L1排名×0.40 + L2排名×0.25 + L3排名×0.25 + L4排名×0.10
综合排名 = 综合分从小到大排序 (越小越好)
```

PEG 权重 10% 且排在最后——深度价值投资不追求成长性，以避坑和安全边际为主要任务。

### 8 家统一排名

所有标的在同一个排名体系内 (`#1~8/8`):
英伟达、苹果、特斯拉、英特尔、AMD、美光、小米(1810.HK)、比特币

### 特殊情况

- **加密货币（BTC）**：L1 用 MVRV Z-Score（反向映射），L2 用算力+网络强度，L3 用改编版 F-Score（链上指标），L4 用减半周期位置
- **港股（小米）**：同一公式但标注跨市场差异
- **困境反转**：统一使用 Non-GAAP Forward Estimate 计算 EBIT/EV 和 ROIC，排名对口径不敏感

### 输出格式

每次分析必须输出四层排名表 + Piotroski F-Score 明细卡 + 投资信号块 + 综合分 + 综合排名。

### 历史演进

- v1.0: Greenblatt 原始（EBIT/EV + ROIC）→ 两层
- v2.0: Greenblatt 扩展（EBIT/EV + ROIC + F-Score 验证不参与排名）→ 三层
- v3.0: 四层加权（L1 40% + L2 25% + L3 25% + L4 10%）→ 当前版本

## 注意事项

- 排名衡量**在当前价格下值不值得买**，非公司优质程度
- 禁止用模型训练数据——所有价格/财务数据必须实时搜索
- 加密货币/港股分析为扩展能力，原生框架为美股
- Skill 配置：`/home/severin/.config/opencode/skills/invest-skill/SKILL.md`
