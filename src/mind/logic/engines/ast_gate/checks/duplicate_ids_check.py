# src/mind/logic/engines/ast_gate/checks/duplicate_ids_check.py

"""Corpus-level duplicate symbol-ID detection for ASTGateEngine.

Enforces ``linkage.duplicate_ids`` — "Symbol identifiers (# ID:) MUST be
globally unique across the entire codebase." This is a CONTEXT-LEVEL check
(it must see every file at once), and — unlike the retired knowledge_gate
mechanism it replaces (#820 Group C) — it is STATELESS: it reads source
files directly via ``AuditorContext.get_files`` rather than the DB knowledge
graph, so it runs in the ``--offline`` audit that CI executes on every push.

The old knowledge_gate check grouped symbols on the capability ``key`` field
(absent from the live graph view, so it never fired) — not the ``# ID:``
anchor the rule is actually about. This detector uses the same anchor regex as
the ``hooks/check_symbol_ids.py`` commit-time backstop, so the two guards agree.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# The CLAUDE.md symbol-ID anchor: "# ID: <uuid-v4>". Placeholder anchors
# ("# ID: xxxxxxxx-...") do not match the hex class and are ignored —
# duplicate detection is about real UUID collisions, not malformed anchors
# (those are the assign_ids/hook concern).
_ID_ANCHOR_RE = re.compile(
    r"#\s*ID:\s*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)

# The rule is scoped to source; the mapping's applies_to is not threaded into
# a context-level check, so the scope is declared here (a symbol-ID anchor only
# ever lives in src/ Python).
_SRC_SCOPE = ["src/**/*.py"]


# ID: ad64d745-9b17-4709-bec7-d84d8d2c1145
def check_duplicate_ids(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    """Flag every ``# ID: <uuid>`` anchor that appears on more than one symbol
    across ``src/``. One BLOCK finding per colliding UUID, listing all sites.
    """
    excludes = params.get("_scope_excludes", []) or []
    id_locations: dict[str, list[str]] = defaultdict(list)

    for file_path in context.get_files(_SRC_SCOPE, excludes):
        try:
            source = file_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(source.splitlines(), start=1):
            match = _ID_ANCHOR_RE.search(line)
            if match:
                id_locations[match.group(1).lower()].append(f"{file_path}:{lineno}")

    findings: list[AuditFinding] = []
    for uuid_val, locations in sorted(id_locations.items()):
        if len(locations) > 1:
            findings.append(
                AuditFinding(
                    check_id="linkage.duplicate_ids",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"Duplicate symbol ID '{uuid_val}' appears "
                        f"{len(locations)} times: {', '.join(locations)}"
                    ),
                    file_path=locations[0].rsplit(":", 1)[0],
                    context={"duplicates": locations},
                )
            )
    return findings
