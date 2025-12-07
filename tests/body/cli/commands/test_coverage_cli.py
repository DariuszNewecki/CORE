# tests/body/cli/commands/test_coverage_cli.py
"""
Tests for the refactored coverage CLI commands.
Refactored to be SYNCHRONOUS to avoid conflicting with @core_command's internal event loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

# Import the actual module to test
import body.cli.commands.coverage as coverage


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def mock_ctx():
    """Creates a mock Typer Context with a valid CoreContext object."""
    mock_git = MagicMock()
    mock_git.repo_path = Path("/tmp/core-repo")

    mock_file_handler = MagicMock()
    mock_file_handler.repo_path = Path("/tmp/core-repo")

    mock_cognitive = MagicMock()
    mock_auditor = MagicMock()

    core_context = SimpleNamespace(
        git_service=mock_git,
        file_handler=mock_file_handler,
        cognitive_service=mock_cognitive,
        auditor_context=mock_auditor,
        # qdrant_service and registry are checked/injected by @core_command
        qdrant_service=MagicMock(),
        registry=None,
    )

    ctx = MagicMock(spec=typer.Context)
    ctx.obj = core_context
    return ctx


# -----------------------------------------------------------------------------
# check command
# -----------------------------------------------------------------------------


def test_check_coverage_success(mock_ctx):
    """check_coverage exits with code 0 when no findings are returned."""
    mock_checker = MagicMock()
    mock_checker.execute = AsyncMock(return_value=[])

    # Mock the CoverageGovernanceCheck class used inside the function
    with patch(
        "body.cli.commands.coverage.CoverageGovernanceCheck", return_value=mock_checker
    ):
        with pytest.raises(typer.Exit) as excinfo:
            # Synchronous call; @core_command handles the async loop
            coverage.check_coverage(mock_ctx)

    assert excinfo.value.exit_code == 0


def test_check_coverage_failure(mock_ctx):
    """check_coverage exits with code 1 when findings are returned."""
    finding = SimpleNamespace(message="Coverage too low", severity="error")
    mock_checker = MagicMock()
    mock_checker.execute = AsyncMock(return_value=[finding])

    with patch(
        "body.cli.commands.coverage.CoverageGovernanceCheck", return_value=mock_checker
    ):
        with pytest.raises(typer.Exit) as excinfo:
            coverage.check_coverage(mock_ctx)

    assert excinfo.value.exit_code == 1


# -----------------------------------------------------------------------------
# report command
# -----------------------------------------------------------------------------


def test_coverage_report_text_only(mock_ctx):
    """coverage_report runs 'coverage report' and prints output."""
    test_path = Path("/tmp/core-repo")

    def fake_run(cmd, cwd, capture_output, text):
        class R:
            returncode = 0
            stdout = "OK\n"
            stderr = ""

        # Basic sanity check
        assert cmd[:2] == ["coverage", "report"]
        assert cwd == test_path
        return R()

    with patch(
        "body.cli.commands.coverage.subprocess.run", side_effect=fake_run
    ) as mock_run:
        # Synchronous call
        coverage.coverage_report(mock_ctx, show_missing=True, html=False)

    assert mock_run.call_count == 1


def test_coverage_report_with_html(mock_ctx):
    """coverage_report with --html also runs 'coverage html'."""
    test_path = Path("/tmp/core-repo")

    def fake_run(cmd, cwd, capture_output, text):
        class R:
            returncode = 0
            stdout = "OK\n"
            stderr = ""

        return R()

    with patch(
        "body.cli.commands.coverage.subprocess.run", side_effect=fake_run
    ) as mock_run:
        coverage.coverage_report(mock_ctx, show_missing=False, html=True)

    # First call: coverage report, second call: coverage html
    assert mock_run.call_count == 2


# -----------------------------------------------------------------------------
# history command
# -----------------------------------------------------------------------------


def test_coverage_history_no_file(mock_ctx, tmp_path):
    """coverage_history handles missing history file gracefully."""
    # Point file handler to temp path where file doesn't exist
    mock_ctx.obj.file_handler.repo_path = tmp_path

    # Should not raise; just print a warning
    coverage.coverage_history(mock_ctx, limit=5)


def test_coverage_history_with_data(mock_ctx, tmp_path):
    """coverage_history prints data from a valid JSON history file."""
    mock_ctx.obj.file_handler.repo_path = tmp_path

    history_dir = tmp_path / "work" / "testing"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "coverage_history.json"

    history_payload = {
        "last_run": {
            "timestamp": "2025-11-22T10:00:00",
            "overall_percent": 48.5,
        },
        "runs": [],
    }
    history_file.write_text(json.dumps(history_payload), encoding="utf-8")

    coverage.coverage_history(mock_ctx, limit=10)


# -----------------------------------------------------------------------------
# target command
# -----------------------------------------------------------------------------


def test_show_targets_uses_policy_config(mock_ctx):
    """show_targets loads the quality_assurance_policy and prints thresholds."""
    fake_policy = {
        "coverage_config": {
            "minimum_threshold": 60,
            "target_threshold": 80,
        }
    }

    with patch(
        "body.cli.commands.coverage.settings.load", return_value=fake_policy
    ) as mock_load:
        coverage.show_targets(mock_ctx)
        mock_load.assert_called_with(
            "charter.policies.governance.quality_assurance_policy"
        )


# -----------------------------------------------------------------------------
# remediate command
# -----------------------------------------------------------------------------


def test_remediate_coverage_single_file_success(mock_ctx, tmp_path):
    """Single-file remediation path should call _remediate_coverage and exit 0."""
    test_file = tmp_path / "src" / "foo.py"

    result_payload = {"status": "completed", "succeeded": 1}

    with patch(
        "body.cli.commands.coverage._remediate_coverage", return_value=result_payload
    ) as mock_remediate:
        # We pass write=True to satisfy the dangerous check in @core_command logic (mocked confirmation)
        # In a real test environment, confirm_action might need patching if not for dangerous=True

        with patch("shared.cli_utils.Confirm.ask", return_value=True):
            coverage.remediate_coverage_cmd(
                mock_ctx,
                file=test_file,
                count=None,
                complexity="simple",
                max_iterations=5,
                batch_size=2,
                write=True,
            )

    # Even though called synchronously in test, @core_command wraps it.
    # Inside the wrapper, it awaits the async function.
    mock_remediate.assert_awaited_once()


# -----------------------------------------------------------------------------
# accumulate commands
# -----------------------------------------------------------------------------


def test_accumulate_tests_command_uses_accumulative_service(mock_ctx):
    """accumulate_tests_command should call AccumulativeTestService."""
    result_payload = {
        "file": "src/core/foo.py",
        "success_rate": 1.0,
        "tests_generated": 3,
        "total_symbols": 3,
        "test_file": "tests/core/test_foo.py",
        "failed_symbols": [],
    }

    # Mock the service class and its async method
    mock_service_instance = MagicMock()
    mock_service_instance.accumulate_tests_for_file = AsyncMock(
        return_value=result_payload
    )

    with patch(
        "features.self_healing.accumulative_test_service.AccumulativeTestService",
        return_value=mock_service_instance,
    ):
        with patch("shared.cli_utils.Confirm.ask", return_value=True):
            coverage.accumulate_tests_command(mock_ctx, "src/core/foo.py", write=True)

    mock_service_instance.accumulate_tests_for_file.assert_called_once_with(
        "src/core/foo.py"
    )


def test_accumulate_batch_command_with_files(mock_ctx, tmp_path):
    """accumulate_batch_command should iterate over discovered files."""
    # Mock repo path in settings to find files
    with patch("body.cli.commands.coverage.settings.REPO_PATH", tmp_path):
        # Create dummy files
        file1 = tmp_path / "src" / "a.py"
        file1.parent.mkdir(parents=True, exist_ok=True)
        file1.touch()

        mock_service_instance = MagicMock()
        mock_service_instance.accumulate_tests_for_file = AsyncMock(
            return_value={"tests_generated": 1}
        )

        with patch(
            "features.self_healing.accumulative_test_service.AccumulativeTestService",
            return_value=mock_service_instance,
        ):
            with patch("shared.cli_utils.Confirm.ask", return_value=True):
                coverage.accumulate_batch_command(
                    mock_ctx, pattern="src/**/*.py", limit=1, write=True
                )

        # Should have processed at least one file
        assert mock_service_instance.accumulate_tests_for_file.call_count >= 1
