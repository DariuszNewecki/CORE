"""A module whose test file leaves public symbols untested is still uncovered.

Found 2026-10-20: the coverage scan reported only modules with no test file.
Once every allowlisted module had one, the test loop went quiet for ten days
while 116 public symbols in 31 modules had no test. The scan now also reports
a module whose test file misses a public symbol, by the same matching the gap
evaluator uses; the runner reports it as missing after a passing run.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from body.evaluators import test_gap_evaluator
from shared.infrastructure.intent.test_coverage_paths import uncovered_source_files
from shared.utils import public_symbols
from shared.utils.public_symbols import has_untested_public_symbols


_CONFIG = {
    "source_root": "src",
    "test_root": "tests",
    "test_file_suffix": "/test_generated.py",
    "excluded_filenames": ["__init__.py"],
    "include_files": [],
    "exempt_modules_without_public_symbols": True,
}


def _repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "partial.py").write_text(
        "def a():\n    return 1\n\ndef b():\n    return 2\n"
    )
    (pkg / "full.py").write_text("class Svc:\n    def run(self):\n        return 1\n")
    for name, body in (
        ("partial", "def test_a():\n    assert True\n"),
        # Class and method credited the way the gap evaluator credits them.
        ("full", "def test_Svc():\n    pass\n\ndef test_run():\n    pass\n"),
    ):
        test_dir = tmp_path / "tests" / "pkg" / name
        test_dir.mkdir(parents=True)
        (test_dir / "test_generated.py").write_text(body)
    return tmp_path


def test_module_with_untested_symbol_is_reported(tmp_path: Path) -> None:
    uncovered = uncovered_source_files(_repo(tmp_path), _CONFIG)
    assert "src/pkg/partial.py" in uncovered


def test_fully_tested_module_is_not_reported(tmp_path: Path) -> None:
    uncovered = uncovered_source_files(_repo(tmp_path), _CONFIG)
    assert "src/pkg/full.py" not in uncovered


def test_unparseable_test_file_counts_as_untested(tmp_path: Path) -> None:
    source = tmp_path / "m.py"
    source.write_text("def a():\n    return 1\n")
    test = tmp_path / "test_m.py"
    test.write_text("def test_a(:\n")
    assert has_untested_public_symbols(source, test) is True


@pytest.mark.asyncio
async def test_scan_agrees_with_gap_evaluator(tmp_path: Path) -> None:
    """The scan reports a module exactly when the evaluator finds gaps."""
    repo = _repo(tmp_path)
    assert test_gap_evaluator.tested_symbol_names is public_symbols.tested_symbol_names
    evaluator = test_gap_evaluator.TestGapEvaluator(repo_root=repo)
    uncovered = set(uncovered_source_files(repo, _CONFIG))
    with patch(
        "body.evaluators.test_gap_evaluator.source_to_test_path",
        side_effect=lambda f: (
            "tests/" + f.removeprefix("src/").removesuffix(".py") + "/test_generated.py"
        ),
    ):
        for source_file in ("src/pkg/partial.py", "src/pkg/full.py"):
            result = await evaluator.execute(source_file=source_file)
            assert bool(result.data["gaps"]) == (source_file in uncovered)


@pytest.mark.asyncio
async def test_runner_reports_passing_file_with_untested_symbols(
    tmp_path: Path,
) -> None:
    from will.workers.test_runner_sensor import TestRunnerSensor

    repo = _repo(tmp_path)
    sensor = TestRunnerSensor()
    sensor._repo_root = repo
    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor.post_artifact_finding = AsyncMock()
    bb = AsyncMock()
    bb.fetch_open_findings.return_value = [
        {"id": "e1", "payload": {"source_file": "src/pkg/partial.py"}},
        {"id": "e2", "payload": {"source_file": "src/pkg/full.py"}},
    ]
    bb.fetch_active_finding_subjects_by_prefix.return_value = set()
    bb.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }
    bb.fetch_awaiting_reaudit_subjects_by_prefix.return_value = set()
    runner = MagicMock()
    runner.run_tests = AsyncMock(return_value={"exit_code": 0, "passed": 1})
    with (
        patch("body.services.service_registry.service_registry") as registry,
        patch(
            "will.workers.test_runner_sensor.load_test_coverage_config",
            return_value=_CONFIG,
        ),
        patch("shared.path_resolver.PathResolver.from_repo"),
        patch("will.phases.canary.pytest_runner.PytestRunner", return_value=runner),
    ):
        registry.get_blackboard_service = AsyncMock(return_value=bb)
        await sensor.run()

    posted = [
        c.kwargs["identity_key_value"]
        for c in sensor.post_artifact_finding.await_args_list
        if c.kwargs["sub_namespace"] == "test.runner.missing"
    ]
    assert posted == ["src/pkg/partial.py"]
