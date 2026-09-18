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
    # The github-annotations format uses severity as the workflow-command
    # title slot (`::error title=<severity>::`), not the rule_id — the rule_id
    # is not part of the line by design (F-10.2 format spec). Assert on the
    # severity title + the rendered message text instead.
    assert "::error title=high::block this" in out
    assert "::notice title=low::fyi" in out
    assert "::notice title=CORE audit summary::" in out
    assert "verdict=FAIL" in out
    assert exc_info.value.exit_code == EXIT_FINDINGS


async def test_offline_json_output_stays_parseable_when_a_log_record_fires(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--format=json stdout parses even when the crash path logs (#828).

    `_run_offline_audit` calls `logger.exception(...)` before emitting the
    JSON error payload. Before #828's fix, the root logger's default
    handlers wrote to stdout, so this log record would land ahead of the
    JSON payload on the same stream and break `json.loads` on the combined
    output — exactly the defect this test guards against.
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
                output_format="json",
            )
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["verdict"] == "ERROR"
    assert "internal error" in parsed["error"]
    assert exc_info.value.exit_code == EXIT_INTERNAL_ERROR


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


# --- #907: skipped BLOCKING rules -> DEGRADED, exit non-success, named ------


def _degraded_by_skip_result() -> dict:
    """F-10.1a-shaped result for the #907 case: every executed rule clean,
    one blocking + one advisory rule skipped."""
    return {
        "verdict": "DEGRADED",
        "passed": False,
        "stats": {
            "total_rules": 10,
            "runnable_rules": 8,
            "skipped_rules_count": 2,
            "skipped_blocking_rules_count": 1,
            "skipped_blocking_rule_ids": [
                "capability.taxonomy.roles_require_canonical_capabilities"
            ],
        },
        "findings": [],
        "executed_rule_ids": [],
        "skipped_rules": [
            {
                "rule_id": "capability.taxonomy.roles_require_canonical_capabilities",
                "engine": "knowledge_gate",
                "enforcement": "blocking",
                "reason": "requires knowledge graph; not available in stateless mode",
            },
            {
                "rule_id": "modularity.unix_philosophy",
                "engine": "llm_gate",
                "enforcement": "advisory",
                "reason": "requires LLM provider + verdict cache",
            },
        ],
        "duration_sec": 0.5,
        "run_id": None,
        "finished_at": "2026-09-18T00:00:00+00:00",
        "mode": "stateless",
    }


async def test_offline_degraded_by_skipped_blocking_rule_exits_findings(
    tmp_path: Path,
) -> None:
    """Governor ruling 3 (#907): DEGRADED uses the existing governed
    non-success exit (EXIT_FINDINGS, as the online path already does for
    `passed=False`), even with zero findings at the severity floor."""
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_degraded_by_skip_result()),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="block",
                output_format="json",
            )
    assert exc_info.value.exit_code == EXIT_FINDINGS


async def test_offline_json_preserves_skipped_blocking_ids_and_reasons(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ruling 4: machine-readable output carries rule ID, enforcement and
    reason for every skipped rule, plus the blocking subset in stats."""
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_degraded_by_skip_result()),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit):
            await _run_offline_audit(
                files=[],
                min_severity_str="block",
                output_format="json",
            )
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == "DEGRADED"
    assert payload["passed"] is False
    by_id = {e["rule_id"]: e for e in payload["skipped_rules"]}
    blocking = by_id["capability.taxonomy.roles_require_canonical_capabilities"]
    assert blocking["enforcement"] == "blocking"
    assert blocking["reason"].startswith("requires knowledge graph")
    assert by_id["modularity.unix_philosophy"]["enforcement"] == "advisory"
    assert payload["stats"]["skipped_blocking_rules_count"] == 1
    assert payload["stats"]["skipped_blocking_rule_ids"] == [
        "capability.taxonomy.roles_require_canonical_capabilities"
    ]


async def test_offline_text_names_skipped_blocking_rules_next_to_verdict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ruling 4/6: the human-readable output names each skipped blocking
    rule and says it was NOT evaluated -- not a dim footnote, never 'PASS'."""
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=_degraded_by_skip_result()),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="block",
                output_format="text",
            )
    out = capsys.readouterr().out
    assert "DEGRADED" in out
    assert "PASS" not in out.replace("DEGRADED, not PASS", "")
    assert "1 blocking rule(s) NOT" in out
    assert "capability.taxonomy.roles_require_canonical_capabilities" in out
    assert "requires knowledge graph" in out
    assert "1 blocking, 1 reporting/advisory" in out
    assert exc_info.value.exit_code == EXIT_FINDINGS


async def test_offline_advisory_only_skips_still_exit_ok(tmp_path: Path) -> None:
    """Ruling 5: an advisory-only skip leaves verdict PASS and exit 0; the
    skip stays visible in the payload but does not gate."""
    result = _result(passed=True)
    result["skipped_rules"][0]["enforcement"] = "advisory"
    result["stats"]["skipped_blocking_rules_count"] = 0
    with (
        patch("cli.resources.code.audit.get_intent_repository") as mock_repo,
        patch("cli.resources.code.audit.get_repo_root", return_value=tmp_path),
        patch(
            "cli.resources.code.audit.run_stateless_audit",
            new=AsyncMock(return_value=result),
        ),
    ):
        mock_repo.return_value = MagicMock()
        with pytest.raises(typer.Exit) as exc_info:
            await _run_offline_audit(
                files=[],
                min_severity_str="block",
                output_format="json",
            )
    assert exc_info.value.exit_code == EXIT_OK
