"""#907 -- the CI gate that consumes the offline audit's JSON verdict.

`core-ci.yml` (static-checks) and `daily_sync.yml` run
`core-admin code audit --offline --severity=block --format=json` and then
gate on the *verdict in the JSON*, never on the exit code alone. Governor's
CI policy (2026-09-18):

- continue only for the canonical verdicts PASS and DEGRADED;
- DEGRADED is explicit (::warning + job summary with the skipped blocking
  rule IDs) and never relabelled PASS;
- fail closed on FAIL, ERROR, a crashed command, malformed/missing JSON, a
  missing/unknown verdict, or any BLOCK-severity finding.

These tests execute the *actual* python block embedded in the workflow
files (extracted by heredoc marker), so a drift in the YAML is a drift in
the test. Both workflows must carry byte-identical gate logic.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = [
    REPO / ".github" / "workflows" / "core-ci.yml",
    REPO / ".github" / "workflows" / "daily_sync.yml",
]
_HEREDOC = re.compile(r"<<'PY'\n(.*?)\nPY\n", re.DOTALL)


def _gate_source(workflow: Path) -> str:
    doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        for step in job.get("steps", []):
            run = step.get("run") or ""
            if "code audit --offline" in run and "--format=json" in run:
                match = _HEREDOC.search(run)
                assert match, f"{workflow.name}: audit step has no PY heredoc gate"
                return match.group(1)
    raise AssertionError(f"{workflow.name}: no offline audit step found")


def _run_gate(
    tmp_path: Path, result: object, raw_exit: int, *, write_json: bool = True
) -> tuple[int, str, str]:
    gate = tmp_path / "gate.py"
    gate.write_text(_gate_source(WORKFLOWS[0]), encoding="utf-8")
    result_path = tmp_path / "offline-audit-result.json"
    if write_json:
        if isinstance(result, str):
            result_path.write_text(result, encoding="utf-8")
        else:
            result_path.write_text(json.dumps(result), encoding="utf-8")
    summary = tmp_path / "summary.md"
    proc = subprocess.run(
        [sys.executable, str(gate), str(result_path), str(raw_exit)],
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary)},
        check=False,
    )
    summary_text = summary.read_text(encoding="utf-8") if summary.exists() else ""
    return proc.returncode, proc.stdout, summary_text


SKIPPED_BLOCKING = [
    {
        "rule_id": "capability.taxonomy.resources_provide_canonical_capabilities",
        "engine": "knowledge_gate",
        "enforcement": "blocking",
        "reason": "requires knowledge graph; not available in stateless mode",
    },
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


def _result(
    verdict: str, *, findings: list | None = None, skipped: list | None = None
) -> dict:
    skipped = skipped if skipped is not None else []
    return {
        "verdict": verdict,
        "passed": verdict == "PASS",
        "stats": {
            "total_rules": 250,
            "runnable_rules": 250 - len(skipped),
            "skipped_rules_count": len(skipped),
            "skipped_blocking_rules_count": sum(
                1 for s in skipped if s["enforcement"] == "blocking"
            ),
        },
        "findings": findings or [],
        "skipped_rules": skipped,
        "mode": "stateless",
    }


def _block_finding() -> dict:
    return {
        "check_id": "architecture.shared.no_layer_imports",
        "severity": "block",
        "file_path": "src/shared/x.py",
        "line_number": 3,
        "message": "shared imports from src/mind",
    }


def test_both_workflows_carry_identical_gate_logic() -> None:
    """Drift guard: the gate is inlined twice; the bytes must not diverge."""
    assert _gate_source(WORKFLOWS[0]) == _gate_source(WORKFLOWS[1])


def test_workflows_parse_as_yaml_and_preserve_the_json_artifact() -> None:
    for wf in WORKFLOWS:
        doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        uploads = [
            step
            for job in doc["jobs"].values()
            for step in job.get("steps", [])
            if "upload-artifact" in str(step.get("uses", ""))
            and "offline-audit-result" in str(step.get("with", {}).get("path", ""))
        ]
        assert uploads, (
            f"{wf.name}: complete JSON result is not preserved as an artifact"
        )
        assert all(step.get("if") == "always()" for step in uploads)


def test_pass_with_exit_zero_continues(tmp_path: Path) -> None:
    """Adopter with fully evaluable blocking law: PASS, no skips, exit 0."""
    code, out, summary = _run_gate(tmp_path, _result("PASS"), 0)
    assert code == 0
    assert "::warning" not in out and "::error" not in out
    assert "CORE offline audit: PASS" in summary


def test_degraded_by_skipped_blocking_rules_continues_with_explicit_warning(
    tmp_path: Path,
) -> None:
    """The real CORE offline shape: DEGRADED, exit 1, three skipped blocking
    rules. Accepted -- with a ::warning and the IDs in the job summary --
    and never relabelled PASS."""
    code, out, summary = _run_gate(
        tmp_path, _result("DEGRADED", skipped=SKIPPED_BLOCKING), 1
    )
    assert code == 0
    assert "::warning title=CORE offline audit DEGRADED::" in out
    assert "DEGRADED (accepted" in summary
    assert "PASS" not in summary.replace("not PASS", "")
    for entry in SKIPPED_BLOCKING:
        assert entry["rule_id"] in out
        assert entry["rule_id"] in summary
        assert entry["reason"] in summary


def test_degraded_with_block_finding_fails_closed(tmp_path: Path) -> None:
    """DEGRADED takes verdict precedence over FAIL (ADR-156 D1a), so a
    genuine BLOCK finding must be caught from the findings, not the verdict."""
    code, out, _ = _run_gate(
        tmp_path,
        _result("DEGRADED", findings=[_block_finding()], skipped=SKIPPED_BLOCKING),
        1,
    )
    assert code == 1
    assert "::error title=architecture.shared.no_layer_imports::" in out
    assert "BLOCK-severity finding(s) present" in out


@pytest.mark.parametrize("verdict", ["FAIL", "ERROR", "BLOCK", "UNKNOWN", "", None])
def test_non_accepted_verdicts_fail_closed(tmp_path: Path, verdict: str | None) -> None:
    result = _result("PASS")
    result["verdict"] = verdict
    if verdict is None:
        del result["verdict"]
    code, out, summary = _run_gate(tmp_path, result, 1)
    assert code == 1
    assert "::error title=CORE offline audit gate::" in out
    assert "FAILED CLOSED" in summary


def test_fail_with_block_finding_fails_closed(tmp_path: Path) -> None:
    code, out, _ = _run_gate(tmp_path, _result("FAIL", findings=[_block_finding()]), 1)
    assert code == 1
    assert "not an accepted stateless verdict" in out


def test_malformed_json_fails_closed(tmp_path: Path) -> None:
    code, out, _ = _run_gate(tmp_path, "{not json", 0)
    assert code == 1
    assert "missing or not JSON" in out


def test_missing_result_file_fails_closed(tmp_path: Path) -> None:
    """A crashed command leaves no result; the gate must not pass on absence."""
    code, out, _ = _run_gate(tmp_path, None, 64, write_json=False)
    assert code == 1
    assert "missing or not JSON" in out


def test_non_object_json_fails_closed(tmp_path: Path) -> None:
    code, out, _ = _run_gate(tmp_path, [], 0)
    assert code == 1
    assert "not a JSON object" in out


def test_pass_with_nonzero_exit_is_inconsistent_and_fails_closed(
    tmp_path: Path,
) -> None:
    code, out, _ = _run_gate(tmp_path, _result("PASS"), 1)
    assert code == 1
    assert "verdict PASS but command exited 1" in out


def test_degraded_with_config_or_internal_exit_fails_closed(tmp_path: Path) -> None:
    for raw_exit in (2, 64):
        code, out, _ = _run_gate(
            tmp_path, _result("DEGRADED", skipped=SKIPPED_BLOCKING), raw_exit
        )
        assert code == 1
        assert f"verdict DEGRADED but command exited {raw_exit}" in out
