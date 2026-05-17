"""批量并行分析测试"""

import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import stock_analysis.batch as batch_module
from stock_analysis.batch import (
    BatchResult,
    BatchSummary,
    _extract_metrics_from_html,
    _generate_batch_summary_html,
    _run_single_analysis,
    _save_batch_summary_json,
    run_batch_analysis,
)
from stock_analysis.cli import parse_company_names


class TestParseCompanyNames:
    def test_single_company(self):
        assert parse_company_names(["script", "英伟达"]) == ["英伟达"]

    def test_multiple_companies_space(self):
        assert parse_company_names(["script", "英伟达", "苹果", "特斯拉"]) == [
            "英伟达",
            "苹果",
            "特斯拉",
        ]

    def test_multiple_companies_comma(self):
        assert parse_company_names(["script", "英伟达,苹果,特斯拉"]) == [
            "英伟达",
            "苹果",
            "特斯拉",
        ]

    def test_multiple_companies_chinese_comma(self):
        assert parse_company_names(["script", "英伟达、苹果、特斯拉"]) == [
            "英伟达",
            "苹果",
            "特斯拉",
        ]

    def test_mixed_separators(self):
        assert parse_company_names(["script", "英伟达,苹果", "特斯拉"]) == [
            "英伟达",
            "苹果",
            "特斯拉",
        ]

    def test_skip_flags(self):
        assert parse_company_names(["script", "英伟达", "--dry-run", "苹果"]) == [
            "英伟达",
            "苹果",
        ]

    def test_skip_subcommands(self):
        assert parse_company_names(["script", "batch", "英伟达", "苹果"]) == [
            "英伟达",
            "苹果",
        ]


class TestBatchResult:
    def test_dataclass_creation(self):
        result = BatchResult(company_name="英伟达")
        assert result.company_name == "英伟达"
        assert result.success is False
        assert result.html_path is None


class TestBatchSummary:
    def test_to_dict(self):
        summary = BatchSummary(
            batch_id="20260101_120000",
            start_time=datetime(2026, 1, 1, 12, 0),
            results=[BatchResult(company_name="英伟达", success=True, score_10=8.5)],
            success_count=1,
            failure_count=0,
        )
        d = summary.to_dict()
        assert d["batch_id"] == "20260101_120000"
        assert d["success_count"] == 1
        assert len(d["results"]) == 1
        assert d["results"][0]["company_name"] == "英伟达"


class TestExtractMetrics:
    def test_extract_from_html(self, tmp_path):
        html = """
        <html>
        <body>
        <div>综合 #2/8</div>
        <div>8.5/10</div>
        <div>F-Score: 7/9</div>
        <div>当前股价: $123.45</div>
        <div>Signal: BULLISH</div>
        <div>Action: BUY</div>
        <div>EBIT/EV: 3.50%</div>
        <div>ROIC: 28.0%</div>
        <div>PEG: 1.10x</div>
        </body>
        </html>
        """
        html_path = tmp_path / "test.html"
        html_path.write_text(html, encoding="utf-8")

        result = BatchResult(company_name="英伟达")
        _extract_metrics_from_html(result, str(html_path))

        assert result.composite_rank == "2/8"
        assert result.score_10 == 8.5
        assert result.f_score == 7
        assert result.price == 123.45
        assert result.signal == "BULLISH"
        assert result.action == "BUY"
        assert result.ebit_ev == "3.50%"
        assert result.roic == "28.0%"
        assert result.peg == "1.10x"

    def test_extract_no_match(self, tmp_path):
        html = "<html><body>无数据</body></html>"
        html_path = tmp_path / "test.html"
        html_path.write_text(html, encoding="utf-8")

        result = BatchResult(company_name="测试")
        _extract_metrics_from_html(result, str(html_path))

        assert result.score_10 is None
        assert result.signal is None


class TestGenerateBatchSummaryHtml:
    def test_generates_html(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_module, "_project_root", tmp_path)

        results = [
            BatchResult(
                company_name="英伟达",
                ticker="NVDA",
                success=True,
                html_path="分析输出/英伟达/test.html",
                score_10=8.5,
                composite_rank="#2/8",
                f_score=7,
                signal="BULLISH",
                action="BUY",
                elapsed_seconds=45.2,
            ),
            BatchResult(
                company_name="苹果",
                ticker="AAPL",
                success=True,
                html_path="分析输出/苹果/test.html",
                score_10=9.0,
                composite_rank="#1/8",
                f_score=8,
                signal="BULLISH",
                action="BUY",
                elapsed_seconds=38.1,
            ),
        ]

        summary = BatchSummary(
            batch_id="20260101_120000",
            start_time=datetime(2026, 1, 1, 12, 0),
            end_time=datetime(2026, 1, 1, 12, 2),
            results=results,
            total_elapsed=83.3,
            success_count=2,
            failure_count=0,
        )

        path = _generate_batch_summary_html(summary)

        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "批次分析汇总" in content
        assert "英伟达" in content
        assert "苹果" in content
        assert "8.5" in content
        assert "9.0" in content
        assert "BULLISH" in content

    def test_generates_with_failures(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_module, "_project_root", tmp_path)

        results = [
            BatchResult(
                company_name="英伟达",
                success=True,
                score_10=8.5,
            ),
            BatchResult(
                company_name="失败公司",
                success=False,
                error="Timeout",
            ),
        ]

        summary = BatchSummary(
            batch_id="20260101_120000",
            start_time=datetime(2026, 1, 1, 12, 0),
            results=results,
            success_count=1,
            failure_count=1,
        )

        path = _generate_batch_summary_html(summary)
        content = Path(path).read_text(encoding="utf-8")
        assert "✅" in content
        assert "❌" in content


class TestSaveBatchSummaryJson:
    def test_saves_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_module, "_project_root", tmp_path)

        summary = BatchSummary(
            batch_id="20260101_120000",
            start_time=datetime(2026, 1, 1, 12, 0),
            results=[BatchResult(company_name="英伟达", success=True)],
            success_count=1,
            failure_count=0,
        )

        path = _save_batch_summary_json(summary)
        assert Path(path).exists()
        import json

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["batch_id"] == "20260101_120000"
        assert data["success_count"] == 1


class TestRunSingleAnalysis:
    @patch("stock_analysis.cli.run_analysis")
    @patch("stock_analysis.registry.name_zh_to_ticker")
    def test_success(self, mock_name_map, mock_run_analysis):
        mock_name_map.return_value = {"英伟达": "NVDA"}
        mock_run_analysis.return_value = "/path/to/report.html"

        result = _run_single_analysis("英伟达")

        assert result.company_name == "英伟达"
        assert result.ticker == "NVDA"
        assert result.success is True
        assert result.html_path == "/path/to/report.html"
        mock_run_analysis.assert_called_once_with("英伟达", dry_run=False, use_opencode_llm=False)

    @patch("stock_analysis.cli.run_analysis")
    @patch("stock_analysis.registry.name_zh_to_ticker")
    def test_failure(self, mock_name_map, mock_run_analysis):
        mock_name_map.return_value = {"英伟达": "NVDA"}
        mock_run_analysis.side_effect = Exception("API Error")

        result = _run_single_analysis("英伟达")

        assert result.company_name == "英伟达"
        assert result.success is False
        assert "API Error" in (result.error or "")


class TestRunBatchAnalysis:
    @patch("stock_analysis.batch.mp.Pool")
    def test_parallel_execution(self, mock_pool_class, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_module, "_project_root", tmp_path)

        # Mock Pool
        mock_pool = MagicMock()
        mock_pool_class.return_value.__enter__.return_value = mock_pool

        # Mock async result
        mock_async = MagicMock()
        mock_async.get.return_value = BatchResult(
            company_name="英伟达",
            ticker="NVDA",
            success=True,
            html_path="/path/to/nvda.html",
            score_10=8.5,
        )
        mock_pool.apply_async.return_value = mock_async

        summary = run_batch_analysis(["英伟达", "苹果"], max_workers=2)

        assert summary.batch_id is not None
        assert summary.success_count == 2
        assert summary.failure_count == 0
        assert len(summary.results) == 2
        assert mock_pool.apply_async.call_count == 2

    def test_empty_companies(self):
        with pytest.raises(ValueError, match="company_names 不能为空"):
            run_batch_analysis([])

    @patch("stock_analysis.batch._generate_batch_summary_html")
    @patch("stock_analysis.batch._save_batch_summary_json")
    @patch("stock_analysis.batch.mp.Pool")
    def test_dry_run_passed(self, mock_pool_class, mock_save, mock_gen, tmp_path, monkeypatch):
        monkeypatch.setattr(batch_module, "_project_root", tmp_path)

        mock_pool = MagicMock()
        mock_pool_class.return_value.__enter__.return_value = mock_pool

        mock_async = MagicMock()
        mock_async.get.return_value = BatchResult(
            company_name="英伟达", ticker="NVDA", success=True
        )
        mock_pool.apply_async.return_value = mock_async

        run_batch_analysis(["英伟达"], dry_run=True, use_opencode_llm=True, max_workers=1)

        # 验证 dry_run 和 use_opencode_llm 被传递
        call_args = mock_pool.apply_async.call_args
        assert call_args[0][1] == ("英伟达", True, True)  # name, dry_run, use_opencode_llm


class TestIntegration:
    """集成测试：验证 end-to-end 流程"""

    @patch("stock_analysis.batch.run_batch_analysis")
    def test_cli_batch_command(self, mock_run_batch, monkeypatch, tmp_path):
        """测试 CLI batch 子命令"""
        from stock_analysis import cli

        mock_run_batch.return_value = BatchSummary(
            batch_id="test",
            start_time=datetime.now(),
            success_count=2,
            failure_count=0,
        )

        monkeypatch.setattr(sys, "argv", ["stock-analysis", "batch", "英伟达", "苹果"])

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 0
        mock_run_batch.assert_called_once()

    @patch("stock_analysis.batch.run_batch_analysis")
    def test_cli_multiple_companies(self, mock_run_batch, monkeypatch, tmp_path):
        """测试 CLI 多公司自动进入批量模式"""
        from stock_analysis import cli

        mock_run_batch.return_value = BatchSummary(
            batch_id="test",
            start_time=datetime.now(),
            success_count=2,
            failure_count=0,
        )

        monkeypatch.setattr(sys, "argv", ["stock-analysis", "英伟达", "苹果"])

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 0
        mock_run_batch.assert_called_once_with(
            ["英伟达", "苹果"], dry_run=False, use_opencode_llm=False
        )

    @patch("stock_analysis.cli.run_analysis")
    def test_cli_single_company_backward_compat(self, mock_run_analysis, monkeypatch, tmp_path):
        """测试单公司向后兼容"""
        from stock_analysis import cli

        mock_run_analysis.return_value = "/path/to/report.html"
        monkeypatch.setattr(sys, "argv", ["stock-analysis", "英伟达"])

        # 单公司模式不调用 sys.exit()，直接运行
        cli.main()

        mock_run_analysis.assert_called_once_with("英伟达", dry_run=False, use_opencode_llm=False)

    @patch("stock_analysis.batch.run_batch_analysis")
    def test_cli_with_options(self, mock_run_batch, monkeypatch, tmp_path):
        """测试带选项的多公司分析"""
        from stock_analysis import cli

        mock_run_batch.return_value = BatchSummary(
            batch_id="test",
            start_time=datetime.now(),
            success_count=2,
            failure_count=0,
        )

        monkeypatch.setattr(sys, "argv", ["stock-analysis", "英伟达", "苹果", "--dry-run", "--use-opencode-llm"])

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 0
        mock_run_batch.assert_called_once_with(
            ["英伟达", "苹果"], dry_run=True, use_opencode_llm=True
        )
