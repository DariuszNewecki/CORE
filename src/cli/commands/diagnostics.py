# src/cli/commands/diagnostics.py

"""
Diagnostic Command Group (Cleaned).

CONSTITUTIONAL PROMOTION (v2.6):
- Evacuated find-clusters and command-tree (Redundant aliases).
- Promoted debug-meta to admin.meta (ConstitutionalPathAnalyzer).
- Promoted unassigned-symbols to symbols.audit.

This file now only houses legacy Verb-First check shims.
"""

from __future__ import annotations

import typer

from cli.logic.diagnostics_policy import policy_coverage
from cli.logic.diagnostics_registry import (
    cli_registry,
    manifest_hygiene,
)


app = typer.Typer(help="System integrity checks and constitutional auditing.")

# Register existing commands (These are still being promoted to Resource Neurons)
app.command("policy-coverage", help="Audits constitution coverage.")(policy_coverage)
app.command("manifest-hygiene", help="Checks capability manifests.")(manifest_hygiene)
app.command("cli-registry", help="Validates CLI registry schema.")(cli_registry)
