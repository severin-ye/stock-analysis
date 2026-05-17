# Phase 1: 开源阻塞项修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 6 个开源阻塞项，使项目可被任何人 clone 后搭建运行

**Architecture:** 从最破坏性的变更（目录重命名）开始，逐步修复路径、依赖、许可证、配置和 gitignore，每个 Task 一次 commit

**Tech Stack:** Python 3.12, git mv, pyproject.toml, pip freeze

---

### Task 1: 重命名 `Stock Kit` → `stock_kit`

**Files:**
- Rename: `Stock Kit/` → `stock_kit/`
- Modify: 所有包含 `Stock Kit` 字样的 Python import、PYTHONPATH、文档引用

**影响范围（7 类引用需更新）：**
1. `sys.path.insert(0, str(Path(__file__).parent.parent))` — 无需改（相对路径，自适应）
2. `PYTHONPATH="Stock Kit"` → `PYTHONPATH="stock_kit"` — 文档和命令
3. `.gitignore` 中无 `Stock Kit` 字样 — 无需改
4. AGENTS.md / README.md / SKILL.md 中所有 `Stock Kit` → `stock_kit`
5. HTML 报告中引用 `Stock Kit/InvestSkill/_template.html` 的 CSS — render.py 模板路径（用 Path 相对推导）
6. companies.json / prices.json 路径由 `Path(__file__).parent.parent / 'data'` — 自适应

- [ ] **Step 1: git mv 目录**
- [ ] **Step 2: 更新 AGENTS.md 中所有 `Stock Kit` → `stock_kit` 引用**
- [ ] **Step 3: 更新 README.md 中所有引用**
- [ ] **Step 4: 更新 SKILL.md 中所有引用**
- [ ] **Step 5: 确认 render.py / validate.py 等路径推导仍然正确**
- [ ] **Step 6: 验证所有 import 仍然工作**
- [ ] **Step 7: Commit**

---

### Task 2: 消除所有硬编码绝对路径

**Files:**
- Modify: `stock_kit/tools/pipeline.py:33`
- Modify: `stock_kit/tools/runtime/report_engine/stages/scaffold.py:22`
- Modify: `stock_kit/tools/runtime/report_engine/pipeline.py:16`
- Modify: `stock_kit/tools/index_generator.py`
- Modify: 6 个测试文件中的硬编码 BASE_DIR

**核心方案：** 所有 `BASE_DIR = Path('/home/severin/Codelib/股市分析')` → 用 `Path(__file__)` 相对推导 + `STOCK_ANALYSIS_HOME` 环境变量 fallback

- [ ] **Step 1: pipeline.py 替换 BASE_DIR**
- [ ] **Step 2: scaffold.py 替换 BASE_DIR**
- [ ] **Step 3: report_engine/pipeline.py 替换 BASE_DIR**
- [ ] **Step 4: index_generator.py 替换 BASE_DIR**
- [ ] **Step 5: 6 个测试文件替换硬编码路径**
- [ ] **Step 6: 更新 AGENTS.md 命令示例添加环境变量说明**
- [ ] **Step 7: 验证路径推导正确**
- [ ] **Step 8: Commit**

---

### Task 3: 创建 pyproject.toml + requirements.txt

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: 创建 requirements.txt**
- [ ] **Step 2: 创建 requirements-dev.txt**
- [ ] **Step 3: 创建 pyproject.toml**
- [ ] **Step 4: 验证 requirements 可安装**
- [ ] **Step 5: Commit**

---

### Task 4: 添加根目录 LICENSE + NOTICE

**Files:**
- Create: `LICENSE` (项目根)
- Create: `NOTICE`
- Modify: `README.md` (添加 License 章节)

- [ ] **Step 1: 创建 LICENSE (MIT, copyright severin)**
- [ ] **Step 2: 创建 NOTICE (第三方归属声明)**
- [ ] **Step 3: 更新 README.md 添加 License 章节**
- [ ] **Step 4: Commit**

---

### Task 5: config.py 环境变量 fallback + .env.example

**Files:**
- Modify: `stock_kit/tools/runtime/report_engine/config.py`
- Create: `.env.example`
- Modify: pipeline.py 中 `get_deepseek_config()` → `get_llm_config()`

- [ ] **Step 1: 修改 config.py 添加环境变量优先读取**
- [ ] **Step 2: 更新 pipeline.py 中 get_deepseek_config → get_llm_config**
- [ ] **Step 3: 创建 .env.example**
- [ ] **Step 4: 验证环境变量 fallback 工作**
- [ ] **Step 5: Commit**

---

### Task 6: 完善 .gitignore + 清理 git 生成产物

**Files:**
- Modify: `.gitignore`
- Remove from git: `stock_kit/data/prices.json`, `.sisyphus/`, `index.html`, 分析输出 HTML
- Create: `stock_kit/data/companies.json.example`

- [ ] **Step 1: 完善 .gitignore**
- [ ] **Step 2: 从 git 移除已追踪的生成产物**
- [ ] **Step 3: 创建 companies.json.example 模板**
- [ ] **Step 4: 验证 git status**
- [ ] **Step 5: Commit**

---

## Phase 2 概览（后续计划）

| # | 任务 | 概要 |
|---|------|------|
| P2-1 | Logger handler 泄漏修复 | `build_logger()` 先清理旧 handler 再添加 |
| P2-2 | PEG 负值映射修复 | 负 PEG → None，不参与排名 |
| P2-3 | yfinance timeout | 用 threading + signal 或 concurrent.futures |
| P2-4 | pipeline 部分失败恢复 | LLM 失败 → 标记 llm_failed=True，不渲染空 HTML |
| P2-5 | validate 数据完整性 | 缺 EBIT/EV 或 F-Score → [Schema] 缺失，影响 passed |
| P2-6 | 消除重复 TICKER_MAP | pipeline.py TICKER_NAME_MAP → 从 company_registry 派生 |

## Phase 3 概览（后续计划）

| # | 任务 | 概要 |
|---|------|------|
| P3-1 | README 安装指南 | 从零搭建步骤 + 快速开始 |
| P3-2 | CONTRIBUTING.md | Python 工具链开发流程 |
| P3-3 | conftest.py + 测试去硬编码 | 共享 fixtures + 路径参数化 |
| P3-4 | ruff + mypy 配置运行 | pyproject.toml 已包含，需首次运行 baseline |
| P3-5 | GitHub Actions CI | lint + typecheck + test |