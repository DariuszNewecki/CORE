# tests/body/atomic/test_assisted_actions__general.py
"""assisted.validate_diff general mode (ADR-168 Amendment 2026-10-10 A3, A5).

A change not born from a finding: CORE chooses the checks. These run against a
real git repository (apply, touched set, ruff) with only the two slow or
shared-state steps replaced — the full audit subprocess and pytest.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from body.atomic.assisted_actions import action_assisted_validate_diff


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _repo(root: Path) -> Path:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "old.py").write_text("x = 1\n")
    (root / "gone.py").write_text("y = 1\n")
    _git(root, "add", "old.py", "gone.py")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _context(root: Path) -> MagicMock:
    worktree = MagicMock()
    worktree.repo_path = str(root)
    worktree.get_current_commit.return_value = "base-sha"
    ctx = MagicMock()
    ctx.git_service.create_worktree.return_value = worktree
    return ctx


_MODIFY_DELETE_ADD_TEST = (
    "diff --git a/old.py b/old.py\n"
    "--- a/old.py\n"
    "+++ b/old.py\n"
    "@@ -1 +1 @@\n"
    "-x = 1\n"
    "+x = 2\n"
    "diff --git a/gone.py b/gone.py\n"
    "deleted file mode 100644\n"
    "--- a/gone.py\n"
    "+++ /dev/null\n"
    "@@ -1 +0,0 @@\n"
    "-y = 1\n"
    "diff --git a/tests/test_new.py b/tests/test_new.py\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/tests/test_new.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def test_ok() -> None:\n"
    "+    assert True\n"
)

_TOUCH_SPECS = (
    "diff --git a/.specs/note.md b/.specs/note.md\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/.specs/note.md\n"
    "@@ -0,0 +1 @@\n"
    "+law\n"
)


async def _validate(
    root: Path,
    patch_text: str,
    audit: tuple[dict[str, Any] | None, str | None],
    tests_ok: bool = True,
) -> tuple[Any, AsyncMock, MagicMock]:
    fn = action_assisted_validate_diff.__wrapped__
    run_tests = AsyncMock(return_value=MagicMock(ok=tests_ok))
    full_audit = MagicMock(return_value=audit)
    with (
        patch("body.atomic.assisted_actions._run_full_audit", full_audit),
        patch("shared.infrastructure.validation.test_runner.run_tests", run_tests),
    ):
        result = await fn(patch=patch_text, general=True, core_context=_context(root))
    return result, run_tests, full_audit


_CLEAN_AUDIT = (
    {
        "verdict": "DEGRADED",
        "findings": [{"severity": "info", "check_id": "x.info"}],
        "skipped_rules": [{"rule_id": "r.needs_db", "enforcement": "blocking"}],
        "class_b": {
            "rules": ["code.tests.no_placeholder_test_body"],
            "checked": ["tests/test_new.py"],
            "violations": [],
        },
    },
    None,
)


# ID: 86405ff5-fa33-4979-aa05-c190abbb6609
async def test_general_refuses_a_patch_touching_governed_text(tmp_path: Path) -> None:
    """A5: governed text (read from the real law) is refused before any audit."""
    result, run_tests, full_audit = await _validate(
        _repo(tmp_path), _TOUCH_SPECS, _CLEAN_AUDIT
    )

    assert result.ok is False
    assert result.data["validation_results"]["governed_text_untouched"] is False
    assert result.data["governed_paths"] == [".specs/note.md"]
    full_audit.assert_not_called()
    run_tests.assert_not_called()


# ID: 7497ce9b-6df3-4f88-9324-98a873351861
async def test_general_passes_and_carries_added_modified_and_deleted(
    tmp_path: Path,
) -> None:
    """A3: every touched file is in the production set — the deletion too —
    ruff skips the deleted file, the touched test file runs under the shared-
    state marker filter, and unevaluated rules are named."""
    result, run_tests, full_audit = await _validate(
        _repo(tmp_path), _MODIFY_DELETE_ADD_TEST, _CLEAN_AUDIT
    )

    assert result.ok is True, result.data
    assert result.data["validation_mode"] == "general"
    assert sorted(result.data["production_set"]) == [
        "gone.py",
        "old.py",
        "tests/test_new.py",
    ]
    assert result.data["validation_results"]["ruff"] is True
    assert result.data["tests_run"] == ["tests/test_new.py"]
    assert run_tests.await_args.kwargs["markers"] == "not trio and not integration"
    assert result.data["not_evaluated"] == [
        {"rule_id": "r.needs_db", "enforcement": "blocking"}
    ]
    assert result.data["validated_base_sha"] == "base-sha"
    # Class B rules get the files that still exist — not the deleted one.
    assert sorted(full_audit.call_args.args[2]) == ["old.py", "tests/test_new.py"]
    assert result.data["validation_results"]["class_b_rules"] is True


# ID: f371017f-847f-48a3-b653-7590416c6c2c
async def test_general_refuses_on_a_blocking_finding(tmp_path: Path) -> None:
    audit = (
        {
            "verdict": "FAIL",
            "findings": [
                {
                    "severity": "blocking",
                    "check_id": "quality.type_safety",
                    "file_path": "old.py",
                    "line_number": 1,
                    "message": "bad",
                }
            ],
            "skipped_rules": [],
        },
        None,
    )
    result, _, _ = await _validate(_repo(tmp_path), _MODIFY_DELETE_ADD_TEST, audit)

    assert result.ok is False
    assert result.data["validation_results"]["full_audit"] is False
    assert result.data["blocking_findings"][0]["rule_id"] == "quality.type_safety"


# ID: 203fdeb2-b4c3-421a-8694-802c00fb53a7
async def test_general_fails_closed_when_the_audit_cannot_run(tmp_path: Path) -> None:
    result, _, _ = await _validate(
        _repo(tmp_path), _MODIFY_DELETE_ADD_TEST, (None, "Full audit timed out")
    )

    assert result.ok is False
    assert result.data["validation_results"]["full_audit"] is False
    assert result.data["audit_error"] == "Full audit timed out"


# ID: 8942bc9f-46dd-4551-a7e0-64604c030128
async def test_general_fails_when_a_test_fails(tmp_path: Path) -> None:
    result, _, _ = await _validate(
        _repo(tmp_path), _MODIFY_DELETE_ADD_TEST, _CLEAN_AUDIT, tests_ok=False
    )

    assert result.ok is False
    assert result.data["validation_results"]["tests"] is False


# ID: b057ba1b-2292-4095-80fa-8930bb27ac58
async def test_general_refuses_on_a_class_b_violation(tmp_path: Path) -> None:
    """Proposal 0011: CORE's write-time test rules bind every producer."""
    audit = (
        {
            **_CLEAN_AUDIT[0],
            "class_b": {
                "rules": ["code.tests.no_placeholder_test_body"],
                "checked": ["tests/test_new.py"],
                "violations": [
                    {
                        "rule_id": "code.tests.no_placeholder_test_body",
                        "file_path": "tests/test_new.py",
                        "message": "no assertion",
                    }
                ],
            },
        },
        None,
    )
    result, _, _ = await _validate(_repo(tmp_path), _MODIFY_DELETE_ADD_TEST, audit)

    assert result.ok is False
    assert result.data["validation_results"]["class_b_rules"] is False
    assert result.data["class_b"]["violations"][0]["file_path"] == "tests/test_new.py"


# ID: 52cf30a4-aee7-47e0-b13d-d04ca02d10d5
async def test_general_fails_closed_without_a_class_b_result(tmp_path: Path) -> None:
    audit = ({k: v for k, v in _CLEAN_AUDIT[0].items() if k != "class_b"}, None)
    result, _, _ = await _validate(_repo(tmp_path), _MODIFY_DELETE_ADD_TEST, audit)

    assert result.ok is False
    assert result.data["validation_results"]["class_b_rules"] is False
