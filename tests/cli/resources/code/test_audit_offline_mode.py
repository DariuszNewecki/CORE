"""F-10.1b — offline audit path tests.

Exercises `_run_offline_audit` directly to avoid wrangling the full
Typer entrypoint. The function is the contract surface CI gates
consume; testing it directly is what catches regressions in exit code
semantics, JSON payload shape, and config/internal error handling.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer

from cli.resources.code.audit import _run_offline_audit
from cli.utils.exit_codes import (
    EXIT_CONFIG_ERROR,
    EXIT_FINDINGS,
    EXIT_INTERNAL_ERROR,
    EXIT_OK,
)


def _result(passed: bool = True, findings: list | None = None) -> dict:
    """Minimal F-10.1a-shaped result for the CLI to render."""
    return {
        "verdict": "PASS" if passed else "FAIL",
        "passed": passed,
        "stats": {"total_rules": 10, "runnable_rules": 8, "skipped_rules_count": 2},
        "findings": findings or [],
        "executed_rule_ids": [],
        "skipped_rules": [
            {"rule_id": "graph.x", "engine": "knowledge_gate", "reason": "..."},
        ],
        "duration_sec": 0.5,
        "run_id": None,
        "finished_at": "2026-06-02T00:00:00+00:00",
        "mode": "stateless",
    }


@pytest.mark.asyncio
async def test_offline_audit_exits_zero_when_no_findings(tmp_path: Path) -> None:
    """No findings >= severity floor -> EXIT_OK (0). The merge-pass path."""
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_result(passed=True)),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="json",
            )
    assert exc_info.value.exit_code == EXIT_OK


@pytest.mark.asyncio
async def test_offline_audit_exits_one_when_blocking_findings(tmp_path: Path) -> None:
    """Findings at or above severity floor -> EXIT_FINDINGS (1). Merge-block."""
    findings = [
        {
            "rule_id": "r.1",
            "file": "src/x.py",
            "line": 5,
            "severity": "high",
            "message": "violation",
        }
    ]
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_result(passed=False, findings=findings)),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="json",
            )
    assert exc_info.value.exit_code == EXIT_FINDINGS


@pytest.mark.asyncio
async def test_offline_audit_exits_config_error_when_intent_repo_fails(
    tmp_path: Path,
) -> None:
    """IntentRepository unreachable -> EXIT_CONFIG_ERROR (2).

    Distinguished from EXIT_FINDINGS so the operator can wire branch
    protection to differentiate "your setup is broken" from "your code
    has violations."
    """
    with (
        patch(
            "cli.resources.code.audit.get_intent_repository",
            side_effect=FileNotFoundError(".intent/ not found"),
        ),
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
    ):
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="text",
            )
    assert exc_info.value.exit_code == EXIT_CONFIG_ERROR


@pytest.mark.asyncio
async def test_offline_audit_exits_internal_error_when_runner_crashes(
    tmp_path: Path,
) -> None:
    """Unexpected exception in run_stateless_audit -> EXIT_INTERNAL_ERROR (64).

    Per ADR-085 §D5, distinct from EXIT_FINDINGS: a crash means the gate
    didn't actually run; the verdict is unknown, not negative.
    """
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="text",
            )
    assert exc_info.value.exit_code == EXIT_INTERNAL_ERROR


@pytest.mark.asyncio
async def test_offline_json_output_emits_f_10_1a_payload_verbatim(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json prints the F-10.1a result dict verbatim on stdout.

    F-10.1b is purely a transport; the runner owns the JSON schema.
    A regression that wrapped or reshaped the payload here would break
    F-10.2 (annotation format) which reads the schema directly.
    """
    payload = _result(passed=True)
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=payload),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit):
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="json",
            )
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["mode"] == "stateless"
    assert parsed["verdict"] == "PASS"
    assert parsed["passed"] is True
    assert "skipped_rules" in parsed
    assert parsed["skipped_rules"][0]["engine"] == "knowledge_gate"


@pytest.mark.asyncio
async def test_offline_audit_passes_files_filter_through(tmp_path: Path) -> None:
    """`--files src/foo.py` reaches run_stateless_audit as the files arg.

    Critical for F-10.5 (pre-commit hook) which invokes with only the
    staged file list to keep latency low. A regression that dropped the
    files filter would make every pre-commit invocation a full audit.
    """
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_result(passed=True)),
        ) as mock_runner,
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit):
            await _run_offline_audit(
                files=["src/foo.py"],
                min_severity_str="high",
                output_format="json",
            )
    mock_runner.assert_called_once()
    assert mock_runner.call_args.kwargs["files"] == ["src/foo.py"]


@pytest.mark.asyncio
async def test_offline_json_error_payload_when_intent_repo_fails(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--json + config error emits structured error payload, not bare text.

    CI consumers parse stdout as JSON unconditionally; emitting Rich
    markup on a config error would break the JSON parser and turn a
    config error into an opaque CI failure.
    """
    with (
        patch(
            "cli.resources.code.audit.get_intent_repository",
            side_effect=FileNotFoundError(".intent/ missing"),
        ),
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
    ):
        with pytest.raises(typer.Exit):
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="json",
            )
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["verdict"] == "ERROR"
    assert parsed["passed"] is False
    assert "configuration error" in parsed["error"]
    assert parsed["mode"] == "stateless"


@pytest.mark.asyncio
async def test_offline_github_annotations_emits_workflow_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--format=github-annotations emits GH workflow-command lines.

    Each finding renders as ::error/::warning/::notice; the summary
    appears last. Exit code semantics unchanged from --format=json.
    """
    findings = [
        {
            "rule_id": "r.high",
            "file": "src/x.py",
            "line": 7,
            "severity": "high",
            "message": "block this",
        },
        {
            "rule_id": "r.low",
            "file": "src/y.py",
            "line": 3,
            "severity": "low",
            "message": "fyi",
        },
    ]
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_result(passed=False, findings=findings)),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="github-annotations",
            )
    out = capsys.readouterr().out
    assert "::error " in out
    assert "r.high" in out
    assert "::notice " in out
    assert "::notice title=CORE audit summary::" in out
    assert "verdict=FAIL" in out
    assert exc_info.value.exit_code == EXIT_FINDINGS


@pytest.mark.asyncio
async def test_offline_github_annotations_error_envelope_on_config_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--format=github-annotations + config error emits ::error workflow command.

    A bare Rich console.print would corrupt the workflow log parser. The
    error path must speak the same protocol as the success path.
    """
    with (
        patch(
            "cli.resources.code.audit.get_intent_repository",
            side_effect=FileNotFoundError(".intent/ missing"),
        ),
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
    ):
        with pytest.raises(typer.Exit):
            await _run_offline_audit(
                files=[],
                min_severity_str="high",
                output_format="github-annotations",
            )
    out = capsys.readouterr().out
    assert out.startswith("::error ")
    assert "configuration error" in out
