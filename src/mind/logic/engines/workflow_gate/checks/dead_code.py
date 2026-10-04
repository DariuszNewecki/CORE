# src/mind/logic/engines/workflow_gate/checks/dead_code.py

"""Dead-code check — delegates subprocess execution to the shared sanctuary.

Issue #585: subprocess invocation was previously inline in this Mind-layer
file (asyncio.create_subprocess_exec on vulture). That placed execution
semantics inside Mind in violation of architecture.layers.no_mind_execution.
The vulture invocation now lives at shared.utils.subprocess_utils.run_vulture
— the canonical subprocess sanctuary — and this module reads the structured
result and turns it into findings.

Findings are per-file ``StructuredViolation``s (ADR-098 D1/D2), like the other
aggregate tool gates. A bare string per vulture line became a project-scope
"System" finding that the audit-violation filter discards, so the rule never
reached the blackboard (2026-10-04 residue investigation).

Classes that ``.intent/`` declares by name (worker ``implementation.class``,
phase ``implementation``) are loaded by import_module, invisible to vulture,
and are passed to it as ignored names. Decorator registrations (CLI commands,
routes, actions) are ignored through the mapping's ``ignore_decorators``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mind.logic.engines.workflow_gate.base_check import (
    StructuredViolation,
    WorkflowCheck,
)
from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger
from shared.path_resolver import PathResolver
from shared.utils.subprocess_utils import run_vulture


logger = getLogger(__name__)

# "src/x.py:12: unused function 'bar' (60% confidence)"
_VULTURE_LINE = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+): (?P<msg>.+)$")
_KIND = re.compile(r"^unused (?P<kind>\w+)|^(?P<code>unreachable) code")
_SAMPLE_CAP = 10


# ID: 6b4cf33a-4fe2-4c5d-9af5-9009d9a52ef8
class DeadCodeCheck(WorkflowCheck):
    """
    Verifies that the codebase is free of dead code using Vulture.
    """

    check_type = "dead_code_check"

    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: 69ab4e1f-14af-467b-8fd1-4e4e14ca0e96
    async def verify(
        self, file_path: Path | None, params: dict[str, Any]
    ) -> list[str | StructuredViolation]:
        # If a specific file is provided, check only that, otherwise check src/
        target = str(file_path) if file_path else "src/"
        kinds = set(params.get("report_kinds") or [])
        try:
            result = await run_vulture(
                target=target,
                repo_root=self._paths.repo_root,
                confidence=params.get("confidence", 80),
                ignore_decorators=list(params.get("ignore_decorators") or []),
                ignore_names=sorted(
                    set(params.get("ignore_names") or [])
                    | _intent_declared_class_names(Path(self._paths.repo_root))
                ),
            )
        except Exception as e:
            return [f"Dead code analysis failed: {e}"]

        files: dict[str, list[tuple[int, str]]] = {}
        for line in result.stdout.strip().splitlines():
            m = _VULTURE_LINE.match(line.strip())
            if not m:
                continue
            k = _KIND.match(m["msg"])
            kind = (k["kind"] or k["code"]) if k else "other"
            if kinds and kind not in kinds:
                continue
            files.setdefault(m["file"], []).append((int(m["line"]), m["msg"]))

        return [
            StructuredViolation(
                file_path=path,
                message=f"{len(issues)} dead-code candidate(s) in {path}",
                context={
                    "tool": "vulture",
                    "issue_count": len(issues),
                    "sample_issues": [
                        f"{path}:{ln}: {msg}" for ln, msg in issues[:_SAMPLE_CAP]
                    ],
                    "first_issue_line": issues[0][0],
                },
            )
            for path, issues in sorted(files.items())
        ]


def _intent_declared_class_names(repo_root: Path) -> set[str]:
    """Class names .intent/ declares for import_module loading."""
    names: set[str] = set()
    try:
        intent = IntentRepository(root=repo_root / ".intent", strict=False)
        for _, doc in intent.iter_documents(under="workers"):
            cls = (doc.get("implementation") or {}).get("class")
            if isinstance(cls, str):
                names.add(cls)
        for _, doc in intent.iter_documents(under="phases"):
            impl = doc.get("implementation")
            if isinstance(impl, str) and "." in impl:
                names.add(impl.rsplit(".", 1)[1])
    except Exception as e:
        logger.warning("dead_code_check: cannot read .intent declarations: %s", e)
    return names
