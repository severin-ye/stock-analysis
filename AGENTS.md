# 股市分析 — 项目知识库

**生成**: 2026-05-10 | **分支**: main

## 概述

美股 + 加密资产综合投资分析项目。基于 InvestSkill v1.6.0（yennanliu，MIT）框架，按 VM Score（价格40% + 质量40% + 安全20%）评分，输出 Markdown 分析 + Chart.js 交互 HTML 报告。

## 目录结构

```
股市分析/
├── AGENTS.md              ← 本文件
├── index.html             ← 导航首页（本地 localhost:8888）
├── InvestSkill/            ← 分析框架源码（MIT，含20个prompt、CSS模板）
│   ├── _template.html      ← HTML 报告 CSS 主模板（所有报告共用）
│   ├── prompts/            ← 20个分析框架（stock-eval, dcf-valuation...）
│   ├── CLAUDE.md           ← InvestSkill 自身的知识库
│   └── output/             ← 示例报告
├── 英伟达/                  ← NVDA（8家公司各含01整体/02过去/03未来 + HTML报告）
├── 苹果/                   ← AAPL
├── 特斯拉/                 ← TSLA
├── 英特尔/                 ← INTC
├── AMD/                    ← AMD
├── 美光/                   ← MU
├── 小米/                   ← 1810.HK
├── 比特币/                 ← BTC
└── .sisyphus/             ← 会话数据
```

## 分析档位（触发词 → 输出）

| 你说 | 出什么 |
|---|---|
| "综合分析"/"出报告" | 1 份 HTML |
| "做研报"/"完整分析" | HTML + 3 MD |
| "快速看下"/"估值" | 1 份 01_整体分析.md |
| "收纳以往分析" | 归档旧分析到 `以往分析/` |
| "重算评分" | 只跑 VM Score |

## 核心规则（每次分析必须遵守）

### 数据采集（先搜后写）
1. marketbeat.com → 股价、PE、市值、YTD
2. trefis.com → 营收、增长驱动
3. 交叉验证 → 至少2个源一致

### 输出格式
- **百分比优先**：涨跌用 `+X%`/`-X%`，目标价辅助
- **涨跌总览表**：固定5列 `维度|涨跌比例|对应价格|概率权重|行业对比`
- **VM Score 明细**：12行 `Price 40% + Quality 40% + Safety 20%`
- **HTML 报告**：8节（S1-S8+verdict），CSS 来自 `InvestSkill/_template.html`
- **HTML 验证（🚨 必须）**：每次生成/修改 HTML 报告后，**必须**运行验证：
  ```bash
  python3 /home/severin/Codelib/股市分析/InvestSkill/validate_html.py <报告路径>
  ```
  验证失败 → 检查缺失 sections → 修复后重新验证。严禁交付未通过验证的 HTML 报告。
  原因：LLM 单次输出长 HTML 容易丢失中间 section（如苹果 260510 报告缺 S3/S4/S6/S7）。

### 批量分析执行策略（🚫 禁止并发派发）
- **3+ 家公司同时分析时，必须逐家自行执行，禁止 `task(background=true)` 并发派发**
- 原因：后台子代理并发槽位仅 1-2 个，多发必饿死
- 正确节奏：搜索→评分→写文件，完成一家再下一家
- 详见 invest-skill SKILL.md "批量分析执行策略" 章节

### 归档
- 公司文件夹→中文名
- 文件命名→`YYMMDD-NN_分析类型.md`
- 新日期分析→旧文件移入 `以往分析/`

## 命令

```bash
# 启动本地预览
cd /home/severin/Codelib/股市分析 && python3 -m http.server 8888
# 访问 http://localhost:8888/index.html

# Git
cd /home/severin/Codelib/股市分析 && git push origin main

# 运行 InvestSkill 测试
cd InvestSkill && npm test
```

## 评分体系

```
综合评分 /10 = (价格40 + 质量40 + 安全20) / 10

价格：DCF安全边际(15) + P/E vs行业(10) + EV/EBITDA(8) + PEG(7)
质量：ROIC vs WACC(12) + 利润率(10) + FCF质量(8) + 护城河(10)
安全：F-Score(10) + 资产负债(5) + 盈利稳定性(5)

8.0+ → 强力推荐  6.5-7.9 → 推荐  5.0-6.4 → 中性
3.5-4.9 → 谨慎  0-3.4 → 回避
```

## 注意事项

- 评分衡量**投资吸引力**（价格+质量+安全），非公司优质程度
- 禁止用模型训练数据——所有价格/财务数据必须实时搜索
- 加密货币/港股分析为扩展能力，原生框架为美股
- Skill 配置：`/home/severin/.config/opencode/skills/invest-skill/SKILL.md`
