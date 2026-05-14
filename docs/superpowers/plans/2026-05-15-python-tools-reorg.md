# Python Tools Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有 Python 运行时代码与测试迁移到 Stock Kit/tools 下，并让 InvestSkill 不再包含任何 `.py` 文件。

**Architecture:** 保留 `tools/` 顶层作为用户入口与项目级工具层，把原 `InvestSkill/report_engine` 迁移到 `tools/runtime/report_engine`，把所有 Python 测试收拢到 `tools/tests`。迁移时统一修正 import、资源路径和测试命令，确保现有 CLI 行为不变。

**Tech Stack:** Python, pytest, pathlib, existing tools pipeline/report engine modules

---

### Task 1: 建立 tools 目录骨架并迁移 runtime 包

**Files:**
- Create: `Stock Kit/tools/runtime/__init__.py`
- Create: `Stock Kit/tools/runtime/report_engine/__init__.py`
- Modify: `Stock Kit/tools/pipeline.py`
- Modify: `Stock Kit/tools/tests/test_pipeline.py`
- Move: `Stock Kit/InvestSkill/report_engine/*.py`
- Move: `Stock Kit/InvestSkill/report_engine/stages/*.py`

- [ ] **Step 1: 写一个失败测试，验证新包路径会被使用**

```python
def test_pipeline_imports_validate_from_runtime_package(monkeypatch):
    import tools.pipeline as pipeline
    module = __import__('tools.runtime.report_engine.stages.validate', fromlist=['validate'])
    monkeypatch.setattr(module, 'validate', lambda report, html_path: (True, []))
    assert callable(module.validate)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH='Stock Kit:Stock Kit/InvestSkill' pytest 'Stock Kit/tools/test_pipeline.py' -q`
Expected: FAIL，原因是 `tools.runtime.report_engine` 尚不存在。

- [ ] **Step 3: 创建新包并移动 report_engine 代码**

```python
# Stock Kit/tools/runtime/__init__.py

# Stock Kit/tools/runtime/report_engine/__init__.py
from tools.runtime.report_engine.pipeline import run
```

- [ ] **Step 4: 把项目入口导入改到新包**

```python
from tools.runtime.report_engine.schema import StockReport, ModuleStatus
from tools.runtime.report_engine.stages.scaffold import scaffold
from tools.runtime.report_engine.stages.render import render_to_file
from tools.runtime.report_engine.stages.validate import validate
```

- [ ] **Step 5: 运行聚焦测试确认通过**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_pipeline.py' -q`
Expected: PASS

### Task 2: 迁移全部 Python 测试到 tools/tests

**Files:**
- Create: `Stock Kit/tools/tests/__init__.py`
- Move: `Stock Kit/tools/test_pipeline.py`
- Move: `Stock Kit/tools/test_ranker.py`
- Move: `Stock Kit/InvestSkill/test_engine.py`
- Move: `Stock Kit/InvestSkill/test_comprehensive.py`
- Move: `Stock Kit/InvestSkill/test_mock_report.py`
- Move: `Stock Kit/InvestSkill/test_validate_crypto.py`

- [ ] **Step 1: 先写失败测试，验证 tools/tests 下可直接发现测试**

```python
def test_snapshot_report_outputs_only_tracks_html_files(tmp_path):
    ...
```

- [ ] **Step 2: 运行单测确认旧路径命令已不再是目标**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_pipeline.py' -q`
Expected: FAIL，直到测试文件和导入路径迁移完成。

- [ ] **Step 3: 移动测试文件并统一 import**

```python
from tools.runtime.report_engine.stages.validate import validate
from tools.runtime.report_engine.stages.scaffold import scaffold
from tools.runtime.report_engine.schema import ChartDef, ChartDataset, ChartType
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_pipeline.py' 'Stock Kit/tools/tests/test_ranker.py' -q`
Expected: PASS

### Task 3: 修正资源路径与旧包名引用

**Files:**
- Modify: `Stock Kit/tools/runtime/report_engine/stages/render.py`
- Modify: `Stock Kit/tools/runtime/report_engine/stages/validate.py`
- Modify: `Stock Kit/tools/runtime/report_engine/pipeline.py`
- Modify: `Stock Kit/tools/pipeline.py`
- Modify: `Stock Kit/README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: 写失败测试，验证模板目录仍能解析**

```python
def test_render_uses_investskill_template_assets():
    from tools.runtime.report_engine.stages.render import TEMPLATE_DIR
    assert TEMPLATE_DIR.exists()
```

- [ ] **Step 2: 运行测试确认失败或暴露错误路径**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_engine.py' -q`
Expected: FAIL，若模板目录或 validate 的 prices.json 路径仍依赖旧目录结构。

- [ ] **Step 3: 改成显式 BASE_DIR 资源定位**

```python
BASE_DIR = Path('/home/severin/Codelib/股市分析')
STOCK_KIT_DIR = BASE_DIR / 'Stock Kit'
INVESTSKILL_DIR = STOCK_KIT_DIR / 'InvestSkill'
TEMPLATE_DIR = INVESTSKILL_DIR / 'templates'
```

- [ ] **Step 4: 更新旧命令文案和文档路径**

```text
PYTHONPATH='Stock Kit' python3 -m tools.pipeline <公司名>
```

- [ ] **Step 5: 运行验证**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_engine.py' 'Stock Kit/tools/tests/test_validate_crypto.py' -q`
Expected: PASS

### Task 4: 清理 InvestSkill 中残留 Python 文件并做总验证

**Files:**
- Delete: `Stock Kit/InvestSkill/report_engine/`
- Delete: `Stock Kit/InvestSkill/test_engine.py`
- Delete: `Stock Kit/InvestSkill/test_comprehensive.py`
- Delete: `Stock Kit/InvestSkill/test_mock_report.py`
- Delete: `Stock Kit/InvestSkill/test_validate_crypto.py`

- [ ] **Step 1: 运行结构检查**

Run: `find 'Stock Kit/InvestSkill' -name '*.py' | sort`
Expected: 无输出

- [ ] **Step 2: 运行相关测试**

Run: `PYTHONPATH='Stock Kit' pytest 'Stock Kit/tools/tests/test_pipeline.py' 'Stock Kit/tools/tests/test_ranker.py' 'Stock Kit/tools/tests/test_validate_crypto.py' 'Stock Kit/tools/tests/test_engine.py' -q`
Expected: PASS

- [ ] **Step 3: 运行命令入口验证**

Run: `PYTHONPATH='Stock Kit' python3 -m tools.pipeline index`
Expected: 成功生成 `index.html`

- [ ] **Step 4: 运行 validate 入口验证**

Run: `PYTHONPATH='Stock Kit' python3 -m tools.pipeline validate '分析输出/以太坊/260513_综合分析报告.html'`
Expected: 输出 `✅ 通过`