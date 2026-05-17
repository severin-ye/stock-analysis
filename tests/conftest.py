"""pytest shared fixtures and configuration"""
import os
from pathlib import Path

import pytest


@pytest.fixture
def base_dir() -> Path:
    """项目根目录 fixture"""
    return Path(os.environ.get(
        'STOCK_ANALYSIS_HOME',
        str(Path(__file__).resolve().parent.parent.parent.parent)
    ))


@pytest.fixture
def output_dir(base_dir) -> Path:
    """分析输出目录 fixture"""
    return base_dir / '分析输出'


@pytest.fixture
def stock_kit_dir(base_dir) -> Path:
    """stock_kit 目录 fixture"""
    return base_dir / 'stock_kit'


@pytest.fixture
def prices_json(stock_kit_dir) -> Path:
    """prices.json 路径 fixture"""
    return stock_kit_dir / 'data' / 'prices.json'
