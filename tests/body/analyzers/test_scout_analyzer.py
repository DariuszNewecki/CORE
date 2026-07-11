# tests/body/analyzers/test_scout_analyzer.py

"""Tests for ScoutAnalyzer — PARSE-phase signal extraction."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from body.analyzers.scout_analyzer import (
    ScoutAnalyzer,
    _extract_repo_signals,
    _format_signal_report,
)
from shared.component_primitive import ComponentPhase


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """Minimal repo with a few Python files."""
    (tmp_path / "main.py").write_text(
        textwrap.dedent("""\
            from __future__ import annotations

            def public_func() -> None:
                print("hello")

            def _private():
                pass
        """),
        encoding="utf-8",
    )
    (tmp_path / "bad.py").write_text(
        textwrap.dedent("""\
            try:
                pass
            except:
                pass
        """),
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# ScoutAnalyzer.execute
# ---------------------------------------------------------------------------


async def test_execute_returns_ok_for_valid_repo(tmp_repo: Path) -> None:
    analyzer = ScoutAnalyzer()
    result = await analyzer.execute(repo_path=tmp_repo)
    assert result.ok is True
    assert result.phase == ComponentPhase.PARSE
    assert "signals_text" in result.data
    assert "signals_raw" in result.data
    assert "cache_key" in result.data
    assert result.data["signals_raw"]["total_py_files"] == 2


async def test_execute_returns_error_for_missing_path() -> None:
    analyzer = ScoutAnalyzer()
    result = await analyzer.execute(repo_path=Path("/nonexistent/path/xyz"))
    assert result.ok is False
    assert "error" in result.data


async def test_execute_accepts_str_path(tmp_repo: Path) -> None:
    analyzer = ScoutAnalyzer()
    result = await analyzer.execute(repo_path=str(tmp_repo))
    assert result.ok is True


# ---------------------------------------------------------------------------
# _extract_repo_signals
# ---------------------------------------------------------------------------


def test_bare_except_detected(tmp_repo: Path) -> None:
    signals = _extract_repo_signals(tmp_repo)
    assert signals["bare_except_count"] >= 1


def test_print_call_detected(tmp_repo: Path) -> None:
    signals = _extract_repo_signals(tmp_repo)
    assert signals["print_call_count"] >= 1


def test_future_annotations_detected(tmp_repo: Path) -> None:
    signals = _extract_repo_signals(tmp_repo)
    assert signals["future_annotations_files"] >= 1


def test_public_def_counted(tmp_repo: Path) -> None:
    signals = _extract_repo_signals(tmp_repo)
    assert signals["public_defs"] >= 1


def test_skips_venv_directory(tmp_path: Path) -> None:
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "hidden.py").write_text("print('secret')")
    (tmp_path / "app.py").write_text("def ok(): pass")
    signals = _extract_repo_signals(tmp_path)
    assert signals["print_call_count"] == 0


# ---------------------------------------------------------------------------
# _format_signal_report
# ---------------------------------------------------------------------------


def test_format_includes_key_fields(tmp_repo: Path) -> None:
    signals = _extract_repo_signals(tmp_repo)
    report = _format_signal_report(signals)
    assert "Python files:" in report
    assert "bare except" in report
    assert "print()" in report
