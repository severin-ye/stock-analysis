# Contributing Guide

感谢你对本项目的兴趣！以下是参与开发的指南。

## 开发环境

```bash
# 1. 克隆仓库
git clone <仓库地址>
cd 股市分析

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装开发依赖
pip install -r requirements.txt -r requirements-dev.txt
```

## 代码规范

本项目使用以下工具保证代码质量：

```bash
# 代码格式化与 lint
ruff check stock_kit/tools/
ruff format stock_kit/tools/

# 类型检查
mypy stock_kit/tools/

# 运行测试
PYTHONPATH="stock_kit" pytest stock_kit/tools/tests/ -v
```

### 提交前必做

1. `ruff check` 通过（无 E/F/W/I 级别错误）
2. `mypy` 无新增类型错误
3. 相关测试通过
4. commit message 遵循约定式提交规范

## Git 提交规范

- 使用中文 commit message
- 前缀：`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`
- 数据变化标注 `旧值 → 新值`，括号附理由
- 示例：`fix: 修复 PEG 负值映射 ( -0.5 → 5.5, 负 PEG 不应视为"最划算")`

## 添加新公司

1. 编辑 `stock_kit/data/companies.json`，添加 ticker 条目
2. 确保 `company_registry.py` 能正确派生所有映射
3. 运行 `PYTHONPATH="stock_kit" python3 -m tools.pipeline <公司名> --dry-run` 验证
4. 运行测试确认无回归

## 目录结构

```
股市分析/
├── stock_kit/              ← 核心引擎
│   ├── tools/              ← Python 运行时
│   │   ├── pipeline.py     ← 主编排器
│   │   ├── fetcher.py      ← 数据采集
│   │   ├── ranker.py       ← 排名计算
│   │   ├── runtime/        ← 报告引擎
│   │   └── tests/          ← 测试
│   ├── InvestSkill/        ← 方法论层（prompts、模板）
│   └── data/               ← 缓存数据（不入 git）
├── 分析输出/               ← 生成报告（不入 git）
└── docs/                   ← 文档和计划
```

## 测试策略

- **单元测试**: `test_ranker.py`（纯数学，无外部依赖）
- **集成测试**: `test_pipeline.py`（需 prices.json 缓存）
- **验证测试**: `test_validate_crypto.py`（验证 HTML 结构）

运行全部测试：

```bash
PYTHONPATH="stock_kit" pytest stock_kit/tools/tests/ -v
```

## 提交 Pull Request

1. 在功能分支上开发：`git checkout -b feat/xxx`
2. 确保 CI 通过（GitHub Actions 会运行 lint + test）
3. 提交 PR，描述变更内容和测试验证结果

## 环境变量

- `STOCK_ANALYSIS_HOME`: 项目根目录（可选，默认自动推导）
- `LLM_API_KEY`: LLM API 密钥
- `LLM_BASE_URL`: LLM API 基础 URL
- `LLM_MODEL`: 模型名称（可选，默认 deepseek-v4-pro）

## 问题反馈

如有问题，请提交 Issue 并附上：
- Python 版本 (`python3 --version`)
- 运行命令和完整错误日志
- `pip freeze` 输出