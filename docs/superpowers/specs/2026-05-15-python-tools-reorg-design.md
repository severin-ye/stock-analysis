# Python 运行时代码迁移到 tools 设计

日期：2026-05-15

## 背景

当前 Python 代码分散在两个区域：

- `Stock Kit/tools/`：项目级数据抓取、排名、首页生成与主分析 pipeline。
- `Stock Kit/InvestSkill/report_engine/` 与 `Stock Kit/InvestSkill/test_*.py`：运行时模块与测试脚本。

这与当前仓库的职责边界不一致。`InvestSkill/` 应只承载 skill 资产与静态资源，不应继续承载 Python 脚本或运行时代码。

## 目标

本次重构要满足以下目标：

1. 所有 Python 脚本与运行时代码统一放入 `Stock Kit/tools/`。
2. `Stock Kit/InvestSkill/` 中不再保留任何 `.py` 文件。
3. `tools/` 内按职责分类，避免继续平铺增长。
4. 保持现有 CLI 用法和核心分析能力可用，必要时只修改导入路径，不改变业务行为。

## 非目标

本次不处理以下事项：

1. 不重写分析逻辑、排名公式或 HTML 模板。
2. 不修改 prompt、skills、Markdown 文档的业务内容，除非为了更新路径说明。
3. 不引入新的运行依赖。

## 目标目录结构

重构后的 Python 目录按职责分为三层：

```text
Stock Kit/tools/
├── __init__.py
├── fetcher.py
├── index_generator.py
├── market_data.py
├── pipeline.py
├── ranker.py
├── runtime/
│   ├── __init__.py
│   └── report_engine/
│       ├── __init__.py
│       ├── config.py
│       ├── pipeline.py
│       ├── schema.py
│       └── stages/
│           ├── __init__.py
│           ├── render.py
│           ├── scaffold.py
│           ├── search.py
│           └── validate.py
└── tests/
    ├── __init__.py
    ├── test_pipeline.py
    ├── test_ranker.py
    ├── test_comprehensive.py
    ├── test_engine.py
    ├── test_mock_report.py
    └── test_validate_crypto.py
```

说明：

- `tools/` 顶层继续承载项目直接调用的工具脚本与主入口。
- `tools/runtime/report_engine/` 承载原来位于 `InvestSkill/report_engine/` 的运行时代码。
- `tools/tests/` 承载所有 Python 测试，不再把测试脚本留在 skill 目录。

## 模块边界

### 1. tools 顶层

保留项目级脚本与用户入口：

- `pipeline.py`
- `fetcher.py`
- `ranker.py`
- `index_generator.py`
- `market_data.py`

这些文件负责：

- 协调数据抓取、排名、报告生成与首页生成。
- 作为 `python -m tools.pipeline` 等入口存在。

### 2. runtime/report_engine

承接原 `InvestSkill/report_engine` 包。

迁移后，所有原先的：

- `from report_engine...`

统一改为：

- `from tools.runtime.report_engine...`

目标是让 report engine 变成 `tools` 的内部运行时模块，而不是 skill 目录的一部分。

### 3. tests

所有 Python 测试集中到 `tools/tests/`。其职责：

- 项目级测试：现有 `tools/test_*.py`
- report engine 测试：原 `InvestSkill/test_*.py`

迁移后不再在 `InvestSkill/` 下运行 Python 测试。

## 迁移规则

### 文件迁移

1. 将 `Stock Kit/InvestSkill/report_engine/` 整体迁移到 `Stock Kit/tools/runtime/report_engine/`。
2. 将 `Stock Kit/InvestSkill/test_engine.py`、`test_comprehensive.py`、`test_mock_report.py`、`test_validate_crypto.py` 迁移到 `Stock Kit/tools/tests/`。
3. 将现有 `Stock Kit/tools/test_pipeline.py`、`test_ranker.py` 一并迁入 `Stock Kit/tools/tests/`，统一测试归档位置。
4. 为新目录补充必要的 `__init__.py`，确保模块可导入。

### 导入规则

统一替换以下导入：

- `from report_engine...` -> `from tools.runtime.report_engine...`
- `import report_engine...` -> `import tools.runtime.report_engine...`

如测试原来依赖 `PYTHONPATH='Stock Kit:Stock Kit/InvestSkill'`，迁移后应收敛为仅依赖 `PYTHONPATH='Stock Kit'`，除非模板或静态资源仍需通过 `InvestSkill` 目录读取。

### 路径与资源规则

report engine 迁移后仍会读取 `InvestSkill/templates/`、`InvestSkill/_template.html` 等静态资源，因此需要保留资源路径，但不再从 `InvestSkill` 导入 Python 包。

若某些模块目前通过相对位置推导模板路径，需要在迁移时显式改为以仓库根目录或 `BASE_DIR` 定位到 `Stock Kit/InvestSkill/...` 静态资源。

## CLI 和兼容性

### 保留的入口

以下命令应继续工作：

- `python -m tools.pipeline <公司名>`
- `python -m tools.pipeline index`
- `python -m tools.pipeline validate <报告路径>`
- `python -m tools.pipeline watch`

### 调整后的入口

原 `python -m report_engine.pipeline <公司名>` 将不再作为主入口保留。若仓库内仍有文档引用，需要统一改为 `python -m tools.pipeline <公司名>` 或新的 `tools.runtime.report_engine.pipeline` 路径。

目标不是维持旧模块名兼容，而是彻底收口到 `tools/`。

## 风险与应对

### 风险 1：导入路径遗漏

影响：测试和 CLI 会出现 `ModuleNotFoundError`。

应对：迁移完成后，对 `report_engine`、`tools.`、`python -m report_engine.pipeline` 做全文搜索并逐项清理。

### 风险 2：模板或输出路径通过 `__file__` 推导

影响：渲染与校验时找不到模板或静态资源。

应对：优先检查 `render.py`、`validate.py`、`config.py` 的路径推导逻辑，必要时改为显式使用 `BASE_DIR / 'Stock Kit' / 'InvestSkill'` 资源路径。

### 风险 3：测试路径变化后命令失效

影响：README、AGENTS、脚本示例中的测试命令过时。

应对：同步更新仓库根 README 和项目知识库中引用到 Python 测试路径或 `PYTHONPATH` 的说明。

## 实施步骤

1. 建立 `tools/runtime/report_engine/` 与 `tools/tests/` 目录骨架。
2. 迁移 report engine 源码文件。
3. 迁移全部 Python 测试文件。
4. 批量修正导入路径。
5. 修正资源路径和 CLI 文案。
6. 更新 README 与必要的仓库文档。
7. 运行聚焦测试和命令验证。

## 验证计划

### 单元与聚焦测试

至少执行以下验证：

1. `pytest 'Stock Kit/tools/tests/test_pipeline.py' -q`
2. `pytest 'Stock Kit/tools/tests/test_ranker.py' -q`
3. `pytest 'Stock Kit/tools/tests/test_validate_crypto.py' -q`
4. `pytest 'Stock Kit/tools/tests/test_engine.py' -q`

### 命令入口验证

至少执行以下命令：

1. `PYTHONPATH='Stock Kit' python3 -m tools.pipeline index`
2. `PYTHONPATH='Stock Kit' python3 -m tools.pipeline validate <报告路径>`

### 结构验证

确认以下条件成立：

1. `Stock Kit/InvestSkill/` 下不存在 `.py` 文件。
2. `Stock Kit/tools/` 下包含全部 Python 代码。
3. 所有 Python 测试从 `tools/tests/` 执行通过。

## 决策结论

采用“一次性全量迁移到 tools，并按职责分层”的方案。

原因：

1. 这是唯一完全满足“skill 不放脚本文件”的方案。
2. 它能把运行时、测试、静态资源三类职责彻底分开。
3. 它避免在 `InvestSkill/` 保留兼容转发层，减少后续维护成本。