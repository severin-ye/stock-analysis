from pathlib import Path

from tools.runtime.report_engine.stages.validate import validate


BASE_DIR = Path('/home/severin/Codelib/股市分析')


def test_eth_report_validation_accepts_pos_crypto_fields():
    html_path = BASE_DIR / '分析输出' / '以太坊' / '260513_综合分析报告.html'

    passed, issues = validate(None, str(html_path))

    assert passed, '\n'.join(issues)