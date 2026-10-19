"""Subprocess probe for the Unit D formatter-runtime correction's sandbox
test (test_format_sandbox_correction.py, ADR-159 Notes).

Runs in a fresh interpreter so get_intent_repository()'s process-wide
singleton is never contaminated by CORE's own already-initialized
.intent/ in the same pytest session -- the same isolation technique
_probe.py (Unit C) already uses. REPO_PATH/MIND are already bound in the
environment by the parent test process.

Constructs a bare CoreContext (registry/knowledge_service/file_service
mocked -- fix.format touches none of them; the registry's session accepts
the audit-record INSERT, since a lost record fails the run (F4);
git_service/file_handler real,
bound to REPO_PATH) and invokes the real, unmodified ActionExecutor
against it directly -- no Proposal, no worker, no database. Exercises
exactly the sandbox execution + propagation path (ADR-071 D2.2) that
Unit D's live run exercises through the full proposal/worker chain, at a
narrower, faster grain.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import MagicMock


class _AcceptingSession:
    """Accepts the audit step's `async with registry.session() as s: async
    with s.begin(): await s.execute(...)` without a database."""

    async def execute(self, *_args, **_kwargs) -> None:
        return None

    def begin(self) -> _AcceptingSession:
        return self

    async def __aenter__(self) -> _AcceptingSession:
        return self

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False


def main() -> int:
    import body.atomic  # noqa: F401 -- triggers action registration
    from body.atomic.executor import ActionExecutor
    from body.infrastructure.storage.file_handler import FileHandler
    from shared.context import CoreContext
    from shared.infrastructure.git_service import GitService

    repo_path = os.environ["REPO_PATH"]
    git_service = GitService(repo_path)
    file_handler = FileHandler(repo_path)
    registry = MagicMock()
    registry.session = _AcceptingSession
    core_context = CoreContext(
        registry=registry,
        git_service=git_service,
        knowledge_service=MagicMock(),
        file_handler=file_handler,
        file_service=MagicMock(),
    )
    executor = ActionExecutor(core_context)

    pre_execution_sha = git_service.get_current_commit()

    result = asyncio.run(
        executor.execute(
            "fix.format",
            write=True,
            pre_execution_sha=pre_execution_sha,
            file_path="package/example.py",
        )
    )
    json.dump({"ok": result.ok, "data": result.data}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
