from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.dead_code import DeadCodeCheck


# ID: 44e41296-bced-4886-b62e-9d8d852e250a
async def test_DeadCodeCheck_verify():
    path_resolver = MagicMock()
    path_resolver.repo_root = "/repo"

    check = DeadCodeCheck(path_resolver)

    fake_result = MagicMock()
    fake_result.stdout = (
        "/repo/src/a.py:10: unused function 'foo'\n"
        "/repo/src/a.py:20: unused variable 'bar'\n"
        "/repo/src/b.py:5: unreachable code\n"
    )

    with (
        patch(
            "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
            new=AsyncMock(return_value=fake_result),
        ),
        patch(
            "mind.logic.engines.workflow_gate.checks.dead_code._intent_declared_class_names",
            return_value=set(),
        ),
    ):
        violations = await check.verify(None, {})

    assert len(violations) == 2
    paths = {v.file_path for v in violations}
    assert paths == {"/repo/src/a.py", "/repo/src/b.py"}
    a = next(v for v in violations if v.file_path == "/repo/src/a.py")
    assert a.context["issue_count"] == 2
    assert a.context["tool"] == "vulture"
