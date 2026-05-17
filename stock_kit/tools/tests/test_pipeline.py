import importlib
from datetime import datetime
from types import SimpleNamespace

import tools.index_generator as index_generator
import tools.pipeline as pipeline
from tools.fetcher import PriceSnapshot


class _DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FixedDateTime:
    @classmethod
    def now(cls):
        return datetime(2026, 5, 15, 12, 0, 0)


def test_run_analysis_regenerates_index_after_report_write(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(pipeline, 'build_logger', lambda company_name: _DummyLogger())
    monkeypatch.setattr(pipeline, 'datetime', _FixedDateTime)
    monkeypatch.setattr(
        pipeline,
        'scaffold',
        lambda company_name: SimpleNamespace(
            ticker='NVDA',
            exchange='NASDAQ',
            asset_category=SimpleNamespace(value='stock'),
            charts=[SimpleNamespace()],
            company_overview=SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        pipeline,
        'fetch_all_8',
        lambda logger=None: {
            'NVDA': PriceSnapshot(
                ticker='NVDA',
                price=123.45,
                pe_ratio='20.1',
                peg_ratio='1.10x',
                ebit_ev='3.50%',
                roic='28.0%',
                f_score=7,
            ),
        },
    )
    monkeypatch.setattr(pipeline, 'build_real_data_prompt', lambda *args, **kwargs: 'prompt')
    monkeypatch.setattr(pipeline, 'run_llm_with_real_data', lambda report, prompt, logger: report)
    monkeypatch.setattr(pipeline, 'apply_authoritative_report_data', lambda report, *args, **kwargs: report)
    monkeypatch.setattr(pipeline, 'apply_real_price_history', lambda report, *args, **kwargs: report)

    rendered_paths = []

    def fake_render_to_file(report, output_path, logger=None):
        rendered_paths.append(output_path)
        return output_path

    monkeypatch.setattr(pipeline, 'render_to_file', fake_render_to_file)

    fetcher = importlib.import_module('tools.fetcher')
    monkeypatch.setattr(fetcher, 'sync_public_data_to_json', lambda logger=None: None)

    validate_module = importlib.import_module('tools.runtime.report_engine.stages.validate')
    monkeypatch.setattr(validate_module, 'validate', lambda report, html_path: (True, []))

    regenerate_calls = []
    monkeypatch.setattr(index_generator, 'regenerate', lambda: regenerate_calls.append('called'))

    html_path = pipeline.run_analysis('英伟达')

    expected_path = tmp_path / '分析输出' / '英伟达' / '260515_综合分析报告.html'
    assert html_path == str(expected_path)
    assert rendered_paths == [str(expected_path)]
    assert regenerate_calls == ['called']


def test_snapshot_report_outputs_only_tracks_html_files(tmp_path):
    output_dir = tmp_path / '分析输出'
    company_dir = output_dir / '英伟达'
    company_dir.mkdir(parents=True)
    html_path = company_dir / '260515_综合分析报告.html'
    html_path.write_text('<html></html>', encoding='utf-8')
    (company_dir / 'notes.txt').write_text('ignore', encoding='utf-8')

    snapshot = pipeline.snapshot_report_outputs(output_dir)

    assert list(snapshot) == [str(html_path.relative_to(output_dir))]


def test_watch_report_outputs_regenerates_index_when_html_changes():
    snapshots = [
        {'英伟达/260515_综合分析报告.html': 1},
        {'英伟达/260515_综合分析报告.html': 2},
    ]
    regenerate_calls = []

    pipeline.watch_report_outputs(
        output_dir=pipeline.BASE_DIR / '分析输出',
        poll_interval=0,
        debounce_seconds=0,
        max_polls=1,
        snapshot_fn=lambda _: snapshots.pop(0),
        regenerate_fn=lambda: regenerate_calls.append('called'),
        sleep_fn=lambda seconds: None,
        logger=_DummyLogger(),
    )

    assert regenerate_calls == ['called']
