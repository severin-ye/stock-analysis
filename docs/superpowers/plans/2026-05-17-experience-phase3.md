# Phase 3: 开源体验 Implementation Plan

**Goal:** 提升开源项目的可用性和开发者体验

---

### Task P3-1: README 安装指南

**文件:** `README.md`
**内容:** 在 README 顶部添加安装/快速开始章节

### Task P3-2: CONTRIBUTING.md

**文件:** `CONTRIBUTING.md`
**内容:** Python 工具链开发流程、测试运行方式、Git 提交规则

### Task P3-3: conftest.py + pytest 配置

**文件:**
- Create: `stock_kit/tools/tests/conftest.py`
- Modify: `pyproject.toml` (pytest 配置已在其中)

**内容:** 共享 fixtures、BASE_DIR fixture、临时目录 fixture

### Task P3-4: ruff + mypy baseline 运行

**命令:**
```bash
ruff check stock_kit/tools/
mypy stock_kit/tools/
```

### Task P3-5: GitHub Actions CI

**文件:** `.github/workflows/ci.yml`
**内容:** Python 3.12 lint + typecheck + test