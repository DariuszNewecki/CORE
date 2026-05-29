# src/mind/logic/engines/cli_gate/base_check.py

"""Base class for cli_gate checks.

A cli_gate check inspects either the walked Typer command registry or a
companion source artifact (the CLI loader, for ``discovery_strict``) and
returns AuditFindings. Checks are synchronous: introspection runs in the
already-async ``verify_context`` and does no I/O of its own.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from shared.models import AuditFinding


# ID: 51b130f9-3765-475f-8925-6358370dda0c
class CliCheck(ABC):
    """Abstract cli_gate check.

    Subclasses set ``check_type`` to the string referenced from the
    mapping's ``params.check_type`` field and implement ``verify``,
    which receives the once-walked command registry and the rule's
    params dict and returns zero-or-more AuditFindings.
    """

    check_type: str

    @abstractmethod
    # ID: f57e6b30-5eea-413b-8bb3-f0961944fb9b
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Return findings for this rule's enforcement.

        Args:
            commands: Output of ``walk_typer_app`` against the live CLI
                application — one dict per command, with a ``callback``
                field carrying the raw function object.
            params: ``rule.params`` from the mapping plus any envelope
                fields the executor adds (e.g. ``_scope_excludes``).
        """
        raise NotImplementedError
