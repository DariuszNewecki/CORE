from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.logic.engines.workflow_gate.checks.alignment import AlignmentVerificationCheck


@pytest.mark.asyncio
# ID: a51442ca-91b8-426c-a2b7-01946bd8e86b
async def test_AlignmentVerificationCheck() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo/root")

    check = AlignmentVerificationCheck(path_resolver)

    file_path = Path("/repo/root/src/foo.py")

    findings: list[dict] = []
    audit_mock = AsyncMock(return_value=(findings, None, None))

    row = MagicMock()
    row.__getitem__ = MagicMock(return_value=True)
    execute_result = MagicMock()
    execute_result.fetchone = MagicMock(return_value=row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)

    context = MagicMock()
    context.db_session = session
    params = {"_context": context}

    with (
        patch("mind.governance.filtered_audit.run_filtered_audit", audit_mock),
        patch("mind.governance.audit_context.AuditorContext", MagicMock()),
    ):
        violations = await check.verify(file_path, params)

    assert violations == []
    audit_mock.assert_awaited_once()
    session.execute.assert_awaited_once()


import pytest


@pytest.mark.asyncio
# ID: 38185345-6f8f-4bd5-b983-8ea6c04ce556
async def test_AlignmentVerificationCheck_verify():
    resolver = MagicMock()
    resolver.repo_root = Path("/repo")

    check = AlignmentVerificationCheck(resolver)

    file_path = Path("/repo/some/file.py")

    db_session = MagicMock()
    exec_result = MagicMock()
    exec_result.fetchone.return_value = (True,)
    db_session.execute = AsyncMock(return_value=exec_result)

    context = MagicMock()
    context.db_session = db_session

    params = {"_context": context}

    with (
        patch(
            "mind.governance.filtered_audit.run_filtered_audit",
            new=AsyncMock(return_value=([], None, None)),
        ),
        patch(
            "mind.governance.audit_context.AuditorContext",
            MagicMock(),
        ),
    ):
        violations = await check.verify(file_path, params)

    assert isinstance(violations, list)
    assert violations == []
    db_session.execute.assert_awaited_once()
