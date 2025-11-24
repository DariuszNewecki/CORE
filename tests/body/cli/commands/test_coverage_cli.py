# tests/body/cli/commands/test_coverage_cli.py
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer


@pytest.fixture
def coverage_module():
    import body.cli.commands.coverage as coverage

    # Reset context to ensure clean state
    coverage._context = None

    # Provide a fake CoreContext with all required services
    # This matches the structure used in src/body/cli/commands/coverage.py
    mock_git = MagicMock()
    mock_git.repo_path = Path("/tmp/core-repo")

    mock_file_handler = MagicMock()
    mock_file_handler.repo_path = Path("/tmp/core-repo")

    fake_ctx = SimpleNamespace(
        repo_path=Path("/tmp/core-repo"),  # Keep for legacy compat
        git_service=mock_git,
        file_handler=mock_file_handler,
        cognitive_service=MagicMock(),
        auditor_context=MagicMock(),
    )
    coverage._context = fake_ctx
    return coverage


# -----------------------------------------------------------------------------
# check command
# -----------------------------------------------------------------------------


def test_check_coverage_success(coverage_module):
    """check_coverage exits with code 0 when no findings are returned."""
    mock_checker = MagicMock()
    mock_checker.execute = AsyncMock(return_value=[])

    with patch.object(
        coverage_module, "CoverageGovernanceCheck", return_value=mock_checker
    ):
        with pytest.raises(typer.Exit) as excinfo:
            coverage_module.check_coverage()

    assert excinfo.value.exit_code == 0


def test_check_coverage_failure(coverage_module):
    """check_coverage exits with code 1 when findings are returned."""
    # We only need something with .message and .severity
    finding = SimpleNamespace(message="Coverage too low", severity="error")

    mock_checker = MagicMock()
    mock_checker.execute = AsyncMock(return_value=[finding])

    with patch.object(
        coverage_module, "CoverageGovernanceCheck", return_value=mock_checker
    ):
        with pytest.raises(typer.Exit) as excinfo:
            coverage_module.check_coverage()

    assert excinfo.value.exit_code == 1


# -----------------------------------------------------------------------------
# report command
# -----------------------------------------------------------------------------


def test_coverage_report_text_only(coverage_module):
    """coverage_report runs 'coverage report' and prints output."""
    fake_ctx = coverage_module._ensure_context()
    # Update path in git_service which is used by report command
    test_path = Path("/tmp/core-repo")
    fake_ctx.git_service.repo_path = test_path

    def fake_run(cmd, cwd, capture_output, text):
        class R:
            returncode = 0
            stdout = "OK\n"
            stderr = ""

        # Basic sanity check on the command
        assert cmd[:2] == ["coverage", "report"]
        assert cwd == test_path
        return R()

    with patch.object(
        coverage_module.subprocess, "run", side_effect=fake_run
    ) as mock_run:
        # show_missing=True, html=False
        coverage_module.coverage_report(show_missing=True, html=False)

    # Only one subprocess call (no HTML)
    assert mock_run.call_count == 1


def test_coverage_report_with_html(coverage_module):
    """coverage_report with --html also runs 'coverage html'."""
    fake_ctx = coverage_module._ensure_context()
    test_path = Path("/tmp/core-repo")
    fake_ctx.git_service.repo_path = test_path

    def fake_run(cmd, cwd, capture_output, text):
        class R:
            returncode = 0
            stdout = "OK\n"
            stderr = ""

        return R()

    with patch.object(
        coverage_module.subprocess, "run", side_effect=fake_run
    ) as mock_run:
        coverage_module.coverage_report(show_missing=False, html=True)

    # First call: coverage report (no --show-missing), second call: coverage html
    assert mock_run.call_count == 2


# -----------------------------------------------------------------------------
# history command
# -----------------------------------------------------------------------------


def test_coverage_history_no_file(coverage_module, tmp_path):
    """coverage_history handles missing history file gracefully."""
    fake_ctx = coverage_module._ensure_context()
    # history command uses file_handler.repo_path
    fake_ctx.file_handler.repo_path = tmp_path

    # Should not raise; just print a warning
    coverage_module.coverage_history(limit=5)


def test_coverage_history_with_data(coverage_module, tmp_path):
    """coverage_history prints data from a valid JSON history file."""
    fake_ctx = coverage_module._ensure_context()
    fake_ctx.file_handler.repo_path = tmp_path

    history_dir = tmp_path / "work" / "testing"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "coverage_history.json"

    history_payload = {
        "last_run": {
            "timestamp": "2025-11-22T10:00:00",
            "overall_percent": 48.5,
            "lines_covered": 100,
            "lines_total": 200,
        },
        "runs": [
            {
                "timestamp": "2025-11-21T10:00:00",
                "overall_percent": 47.0,
                "delta": -1.5,
                "lines_covered": 94,
                "lines_total": 200,
            }
        ],
    }
    history_file.write_text(json.dumps(history_payload), encoding="utf-8")

    # Should read and render the history without raising
    coverage_module.coverage_history(limit=10)


# -----------------------------------------------------------------------------
# target command
# -----------------------------------------------------------------------------


def test_show_targets_uses_policy_config(coverage_module, monkeypatch):
    """show_targets loads the quality_assurance_policy and prints thresholds."""
    # Fake settings.load to return a policy with coverage_config
    fake_policy = {
        "coverage_config": {
            "minimum_threshold": 60,
            "target_threshold": 80,
            "critical_paths": ["src/core/*", "src/mind/*"],
        }
    }

    def fake_load(key: str):
        assert "quality_assurance_policy" in key
        return fake_policy

    monkeypatch.setattr(coverage_module, "settings", SimpleNamespace(load=fake_load))

    # Should not raise; just print information
    coverage_module.show_targets()


# -----------------------------------------------------------------------------
# remediate command (error branches + happy path)
# -----------------------------------------------------------------------------


def test_remediate_coverage_invalid_complexity(coverage_module):
    """Invalid complexity should exit with code 1 without calling remediation."""
    with pytest.raises(typer.Exit) as excinfo:
        coverage_module.remediate_coverage_cmd(
            file=None,
            count=None,
            complexity="weird",  # invalid
            max_iterations=5,
            batch_size=2,
            write=False,
        )
    assert excinfo.value.exit_code == 1


def test_remediate_coverage_conflicting_file_and_count(coverage_module, tmp_path):
    """Using both --file and --count should exit with code 1."""
    test_file = tmp_path / "src" / "foo.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("print('hello')\n")

    with pytest.raises(typer.Exit) as excinfo:
        coverage_module.remediate_coverage_cmd(
            file=test_file,
            count=5,
            complexity="simple",
            max_iterations=5,
            batch_size=2,
            write=False,
        )
    assert excinfo.value.exit_code == 1


def test_remediate_coverage_single_file_success(coverage_module, tmp_path):
    """Single-file remediation path should call _remediate_coverage and exit 0."""
    fake_ctx = coverage_module._ensure_context()
    # Ensure dependencies for remediation are set
    fake_ctx.file_handler.repo_path = tmp_path

    test_file = tmp_path / "src" / "foo.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("print('hello')\n")

    result_payload = {
        "total": 1,
        "succeeded": 1,
        "failed": 0,
        "final_coverage": 80.0,
        "status": "completed",
    }

    with patch.object(
        coverage_module, "_remediate_coverage", AsyncMock(return_value=result_payload)
    ) as mock_remediate:
        with pytest.raises(typer.Exit) as excinfo:
            coverage_module.remediate_coverage_cmd(
                file=test_file,
                count=None,
                complexity="simple",
                max_iterations=5,
                batch_size=2,
                write=False,
            )

    assert excinfo.value.exit_code == 0
    mock_remediate.assert_awaited_once()


# -----------------------------------------------------------------------------
# accumulate / accumulate-batch commands
# -----------------------------------------------------------------------------


def test_accumulate_tests_command_uses_accumulative_service(
    coverage_module, tmp_path, monkeypatch
):
    """accumulate_tests_command should call AccumulativeTestService for the file."""
    # Ensure context has a cognitive_service
    fake_ctx = coverage_module._ensure_context()
    fake_ctx.cognitive_service = MagicMock()

    result_payload = {
        "file": "src/core/foo.py",
        "success_rate": 1.0,
        "tests_generated": 3,
        "total_symbols": 3,
        "test_file": "tests/core/test_foo.py",
        "failed_symbols": [],
    }

    calls: list[str] = []

    async def fake_accumulate(self, file_path: str):
        calls.append(file_path)
        return result_payload

    # Patch the AccumulativeTestService in the real module it is imported from
    import features.self_healing.accumulative_test_service as acc_mod

    # Use a real class or Mock, but attach the method
    class FakeService:
        def __init__(self, cognitive_service):
            assert cognitive_service is fake_ctx.cognitive_service

        accumulate_tests_for_file = fake_accumulate

    monkeypatch.setattr(acc_mod, "AccumulativeTestService", FakeService)

    # Run the command (synchronous wrapper around asyncio.run)
    coverage_module.accumulate_tests_command("src/core/foo.py")

    # Our fake async method should have been called exactly once with the given path
    assert calls == ["src/core/foo.py"]


def test_accumulate_batch_command_with_files(coverage_module, tmp_path, monkeypatch):
    """accumulate_batch_command should iterate over discovered files and call service."""
    # Point REPO_PATH to a temp repo root with some fake files
    repo_root = tmp_path
    monkeypatch.setattr(coverage_module.settings, "REPO_PATH", repo_root)

    # Create a few Python files matching the pattern "src/**/*.py"
    file1 = repo_root / "src" / "a.py"
    file2 = repo_root / "src" / "nested" / "b.py"
    file1.parent.mkdir(parents=True, exist_ok=True)
    file2.parent.mkdir(parents=True, exist_ok=True)
    file1.write_text("print('a')\n")
    file2.write_text("print('b')\n")

    fake_ctx = coverage_module._ensure_context()
    fake_ctx.cognitive_service = MagicMock()

    calls: list[str] = []

    async def fake_accumulate(self, file_path: str):
        calls.append(file_path)
        # Return a minimal but valid result dict
        return {
            "file": file_path,
            "success_rate": 1.0,
            "tests_generated": 1,
            "total_symbols": 1,
            "test_file": f"tests/{file_path.replace('/', '_')}",
            "failed_symbols": [],
        }

    import features.self_healing.accumulative_test_service as acc_mod

    class FakeService:
        def __init__(self, cognitive_service):
            assert cognitive_service is fake_ctx.cognitive_service

        accumulate_tests_for_file = fake_accumulate

    monkeypatch.setattr(acc_mod, "AccumulativeTestService", FakeService)

    # Explicitly pass a string pattern so Path.glob() gets a proper value
    coverage_module.accumulate_batch_command(pattern="src/**/*.py", limit=2)

    # We expect both files (as relative paths from REPO_PATH) to have been processed
    assert len(calls) == 2
    assert set(calls) == {
        str(file1.relative_to(repo_root)),
        str(file2.relative_to(repo_root)),
    }
