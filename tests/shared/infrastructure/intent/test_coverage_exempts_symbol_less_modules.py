"""Modules with no public testable symbols are exempt from "test file required".

Governor ruling 2026-10-03 (CORE-TestGovernance.md, test_coverage.yaml
``exempt_modules_without_public_symbols``): for the ADR-133 symbol-governed
pipeline such a module is not test-coverage work. Found when five modules
looped: the coverage scan required a test file while TestGapEvaluator, by
ADR-133 D2, had nothing to test in them. The predicate is shared, so the scan
and the evaluator cannot diverge.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from body.evaluators import test_gap_evaluator
from shared.infrastructure.intent import test_coverage_paths
from shared.infrastructure.intent.test_coverage_paths import uncovered_source_files
from shared.utils import public_symbols


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
    (pkg / "private_only.py").write_text("def _helper():\n    return 1\n")
    (pkg / "shim.py").write_text('"""Re-export shim."""\nfrom os import path\n')
    (pkg / "public.py").write_text("def run():\n    return 1\n")
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_zero_public_symbol_module_without_test_is_not_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    uncovered = uncovered_source_files(repo, _CONFIG)
    assert "src/pkg/private_only.py" not in uncovered
    assert "src/pkg/shim.py" not in uncovered


def test_module_with_public_symbol_without_test_is_still_reported(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    assert "src/pkg/public.py" in uncovered_source_files(repo, _CONFIG)


def test_switch_off_keeps_the_previous_behaviour(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    config = {**_CONFIG, "exempt_modules_without_public_symbols": False}
    uncovered = set(uncovered_source_files(repo, config))
    assert {
        "src/pkg/private_only.py",
        "src/pkg/shim.py",
        "src/pkg/public.py",
    } <= uncovered


@pytest.mark.asyncio
async def test_runner_reaudit_resolves_rows_for_newly_exempt_modules(
    tmp_path: Path,
) -> None:
    """The runner's quarantine drain uses the same scan as current truth, so
    an already-open missing-row for an exempt module is no longer current
    (and is resolved), while a public module's row stays current."""
    from will.workers.test_runner_sensor import TestRunnerSensor

    repo = _repo(tmp_path)
    sensor = TestRunnerSensor()
    sensor._repo_root = repo
    sensor.post_report = AsyncMock()
    bb = AsyncMock()
    bb.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }
    bb.fetch_awaiting_reaudit_subjects_by_prefix.return_value = set()
    with patch("body.services.service_registry.service_registry") as registry:
        registry.get_blackboard_service = AsyncMock(return_value=bb)
        await sensor._adjudicate_test_quarantine(_CONFIG)

    current = bb.adjudicate_awaiting_reaudit_findings.await_args_list[0].kwargs[
        "current_violation_subjects"
    ]
    assert "python::test.runner.missing::src/pkg/public.py" in current
    assert "python::test.runner.missing::src/pkg/private_only.py" not in current


def test_scan_and_gap_evaluator_share_one_predicate(tmp_path: Path) -> None:
    """Structural: both import the predicate from shared.utils.public_symbols.
    Behavioural: on the same module they see the same public symbols."""
    assert (
        test_gap_evaluator.extract_public_symbols
        is public_symbols.extract_public_symbols
    )
    assert (
        test_coverage_paths.has_public_testable_symbols
        is public_symbols.has_public_testable_symbols
    )
    module = tmp_path / "m.py"
    module.write_text(
        "def a(): pass\n"
        "def _b(): pass\n"
        "class C:\n"
        "    def __init__(self): pass\n"
        "    def go(self): pass\n"
        "    def _hidden(self): pass\n"
    )
    evaluator_names = [
        s.name for s in test_gap_evaluator._extract_public_symbols(module)
    ]
    shared_names = [s.name for s in public_symbols.extract_public_symbols(module)]
    assert evaluator_names == shared_names == ["a", "C", "C.go"]


def test_unparseable_module_is_never_exempted(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n")
    assert public_symbols.has_public_testable_symbols(bad) is True
