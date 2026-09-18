"""#907 -- the GitHub Action entrypoint derives its verdict from JSON.

`entrypoint.sh` (the `core-audit-gate` Docker action, F-10.3) used to map
exit code 1 -> FAIL, which would report a DEGRADED offline audit as FAIL
and contradict #907. It now runs the audit with --format=json, keeps the
complete result, and derives `verdict=` from the JSON:

    PASS      -> exit 0 (only if the CLI exited 0; otherwise ERROR / 64)
    DEGRADED  -> exit 1 (preserved as DEGRADED, ::warning with skipped IDs)
    FAIL      -> exit 1
    ERROR     -> CLI exit (2 / 64), forced non-zero
    unknown / malformed / missing JSON / crashed command -> ERROR, exit 64

Driven end to end with a fake `core-admin` on PATH that emits a canned
payload and exit code, so the mapping is tested against the real script.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO / "entrypoint.sh"

SKIPPED_BLOCKING = [
    {
        "rule_id": "capability.taxonomy.roles_require_canonical_capabilities",
        "engine": "knowledge_gate",
        "enforcement": "blocking",
        "reason": "requires knowledge graph; not available in stateless mode",
    },
    {
        "rule_id": "runtime.worker_max_interval_within_observed",
        "engine": "runtime_gate",
        "enforcement": "blocking",
        "reason": "requires db_session; not available in stateless mode",
    },
]


def _payload(
    verdict: str, *, findings: list | None = None, skipped: list | None = None
) -> str:
    skipped = skipped or []
    return json.dumps(
        {
            "verdict": verdict,
            "passed": verdict == "PASS",
            "stats": {
                "total_rules": 10,
                "runnable_rules": 10 - len(skipped),
                "skipped_rules_count": len(skipped),
                "skipped_blocking_rules_count": sum(
                    1 for s in skipped if s["enforcement"] == "blocking"
                ),
            },
            "findings": findings or [],
            "skipped_rules": skipped,
            "mode": "stateless",
        }
    )


def _run(
    tmp_path: Path,
    *,
    stdout: str | None,
    exit_code: int,
    fmt: str = "github-annotations",
    github_actions: bool = True,
) -> tuple[int, str, str]:
    """Run entrypoint.sh with a fake core-admin; return (exit, stdout, GITHUB_OUTPUT)."""
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    shim = shim_dir / "core-admin"
    shim.write_text(
        "#!/bin/bash\n"
        '[ -n "$FAKE_STDOUT_FILE" ] && cat "$FAKE_STDOUT_FILE"\n'
        'exit "${FAKE_EXIT:-0}"\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    fake_out = tmp_path / "fake_stdout.json"
    if stdout is not None:
        fake_out.write_text(stdout, encoding="utf-8")

    workspace = tmp_path / "workspace"
    (workspace / ".intent").mkdir(parents=True)
    output_file = tmp_path / "github_output"
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir()

    env = {
        **os.environ,
        # shim first, then the interpreter running these tests (so the
        # runtime's own formatter is importable by `python3`), then the rest.
        "PATH": os.pathsep.join(
            [
                str(shim_dir),
                str(Path(sys.executable).parent),
                os.environ.get("PATH", ""),
            ]
        ),
        "FAKE_STDOUT_FILE": str(fake_out) if stdout is not None else "",
        "FAKE_EXIT": str(exit_code),
        "GITHUB_ACTIONS": "true" if github_actions else "",
        "GITHUB_WORKSPACE": str(workspace),
        "GITHUB_OUTPUT": str(output_file),
        "RUNNER_TEMP": str(runner_temp),
        "INPUT_FORMAT": fmt,
        "INPUT_SEVERITY": "block",
    }
    proc = subprocess.run(
        ["bash", str(ENTRYPOINT)], capture_output=True, text=True, env=env, check=False
    )
    gh_out = output_file.read_text(encoding="utf-8") if output_file.exists() else ""
    return proc.returncode, proc.stdout + proc.stderr, gh_out


def test_pass_is_pass_exit_zero(tmp_path: Path) -> None:
    """Adopter with fully evaluable blocking law still receives PASS."""
    code, out, gh = _run(tmp_path, stdout=_payload("PASS"), exit_code=0)
    assert code == 0
    assert "verdict=PASS" in gh
    assert "Verdict: PASS (exit 0" in out
    assert "::warning" not in out


def test_degraded_is_preserved_as_degraded_not_fail(tmp_path: Path) -> None:
    code, out, gh = _run(
        tmp_path, stdout=_payload("DEGRADED", skipped=SKIPPED_BLOCKING), exit_code=1
    )
    assert code == 1
    assert "verdict=DEGRADED" in gh
    assert "verdict=FAIL" not in gh and "verdict=PASS" not in gh
    assert "::warning title=CORE audit DEGRADED::" in out
    for entry in SKIPPED_BLOCKING:
        assert entry["rule_id"] in out
    # rendered annotations come from the runtime's own formatter
    assert (
        "::warning title=Blocking rule NOT evaluated: runtime.worker_max_interval_within_observed"
        in out
    )
    assert "verdict=DEGRADED" in out


def test_fail_is_fail_exit_one(tmp_path: Path) -> None:
    finding = {
        "check_id": "r.block",
        "severity": "block",
        "file_path": "src/x.py",
        "line_number": 5,
        "message": "violation",
    }
    code, out, gh = _run(
        tmp_path, stdout=_payload("FAIL", findings=[finding]), exit_code=1
    )
    assert code == 1
    assert "verdict=FAIL" in gh
    assert "::error" in out and "violation" in out


def test_error_verdict_keeps_config_exit_code(tmp_path: Path) -> None:
    code, _, gh = _run(tmp_path, stdout=_payload("ERROR"), exit_code=2)
    assert code == 2
    assert "verdict=ERROR" in gh


@pytest.mark.parametrize("verdict", ["BLOCK", "UNKNOWN", ""])
def test_unknown_verdict_fails_closed(tmp_path: Path, verdict: str) -> None:
    code, out, gh = _run(tmp_path, stdout=_payload(verdict), exit_code=0)
    assert code == 64
    assert "verdict=ERROR" in gh
    assert "::error title=CORE audit ERROR::" in out


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    code, _, gh = _run(tmp_path, stdout="{not json", exit_code=0)
    assert code == 64
    assert "verdict=ERROR" in gh


def test_crashed_command_with_no_output_fails_closed(tmp_path: Path) -> None:
    code, _, gh = _run(tmp_path, stdout=None, exit_code=64)
    assert code == 64
    assert "verdict=ERROR" in gh


def test_pass_with_nonzero_exit_is_inconsistent_and_fails_closed(
    tmp_path: Path,
) -> None:
    code, _, gh = _run(tmp_path, stdout=_payload("PASS"), exit_code=1)
    assert code == 64
    assert "verdict=ERROR" in gh


def test_degraded_with_exit_zero_is_forced_nonzero(tmp_path: Path) -> None:
    """A DEGRADED verdict never exits success, whatever the CLI did."""
    code, _, gh = _run(
        tmp_path, stdout=_payload("DEGRADED", skipped=SKIPPED_BLOCKING), exit_code=0
    )
    assert code == 1
    assert "verdict=DEGRADED" in gh


def test_json_format_emits_the_complete_result(tmp_path: Path) -> None:
    payload = _payload("DEGRADED", skipped=SKIPPED_BLOCKING)
    code, out, _ = _run(tmp_path, stdout=payload, exit_code=1, fmt="json")
    assert code == 1
    json_line = next(line for line in out.splitlines() if line.startswith("{"))
    assert json.loads(json_line) == json.loads(payload)


def test_text_format_renders_verdict_and_skipped_blocking(tmp_path: Path) -> None:
    code, out, _ = _run(
        tmp_path,
        stdout=_payload("DEGRADED", skipped=SKIPPED_BLOCKING),
        exit_code=1,
        fmt="text",
    )
    assert code == 1
    assert "DEGRADED" in out
    assert "runtime.worker_max_interval_within_observed" in out
