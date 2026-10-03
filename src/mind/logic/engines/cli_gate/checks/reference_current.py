# src/mind/logic/engines/cli_gate/checks/reference_current.py

"""Verifies cli.reference_current (ADR-167 D2): the generated CLI reference
pages equal what ``build_reference_pages`` renders from the live trees.

Deterministic, no false positives: the rule and ``core-admin docs generate``
share one builder. When core-cli is not installed the ``core`` page is not
compared and the check says so in a finding; it never passes with the
comparison skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.cli.reference_markdown import (
    CORE_CLI_PAGE,
    Command,
    build_reference_pages,
    click_command_for,
    load_core_cli_tree,
)
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


_CHECK_ID = "cli_gate.reference_current"
_REMEDY = "Regenerate with `core-admin docs generate --write`."


# ID: 8fe96803-43a7-4d3d-a8c9-5e3e4c33d2d1
def live_core_admin_tree() -> Command:
    """The running core-admin click tree."""
    # Deferred like CliGateEngine._walk_registry: importing the app pulls in
    # the whole CLI graph, which engine discovery must not trigger.
    from cli.admin_cli import app

    return click_command_for(app)


# ID: fa9f67d9-72f1-492f-ba17-8bdfff4d2f0c
class ReferenceCurrentCheck(CliCheck):
    check_type = "reference_current"

    # ID: b240b1c4-0ad0-48aa-a5b4-3bc4fe0444bc
    def __init__(
        self,
        path_resolver: PathResolver,
        core_admin_tree: Callable[[], Command] = live_core_admin_tree,
        core_cli_tree: Callable[[], tuple[Command, str] | None] = load_core_cli_tree,
    ) -> None:
        self._path_resolver = path_resolver
        self._core_admin_tree = core_admin_tree
        self._core_cli_tree = core_cli_tree

    # ID: cd6fd3cc-d642-4391-950b-f63d65f97bc8
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        core_cli = self._core_cli_tree()
        pages = build_reference_pages(self._core_admin_tree(), core_cli)
        repo_root = self._path_resolver.repo_root
        findings: list[AuditFinding] = []

        for rel_path, expected in pages.items():
            target = repo_root / rel_path
            if not target.is_file():
                message = f"Generated CLI reference {rel_path} is missing. {_REMEDY}"
            elif target.read_text(encoding="utf-8") != expected:
                message = (
                    f"Generated CLI reference {rel_path} does not match the live "
                    f"command tree. {_REMEDY}"
                )
            else:
                continue
            findings.append(
                AuditFinding(
                    check_id=_CHECK_ID,
                    severity=AuditSeverity.INFO,
                    message=message,
                    file_path=rel_path,
                    context={"page": rel_path},
                )
            )

        if core_cli is None:
            findings.append(
                AuditFinding(
                    check_id=_CHECK_ID,
                    severity=AuditSeverity.INFO,
                    message=(
                        f"{CORE_CLI_PAGE} was not compared: core-cli is not installed "
                        "here. Install the released package "
                        "(`pip install --no-deps core-cli`)."
                    ),
                    file_path=CORE_CLI_PAGE,
                    context={"page": CORE_CLI_PAGE, "not_compared": True},
                )
            )
        return findings
