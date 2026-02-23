# src/body/cli/resources/__init__.py
"""
Resource-first CLI command modules.

Constitutional Alignment:
- Commands organized by resource (database, vectors, code, etc.)
- No exposure of internal architecture layers (mind/body/will)
- Resource-action pattern enforced at registration

Structure:
    database/    - PostgreSQL operations
    vectors/     - Qdrant vector operations
    code/        - Codebase operations
    symbols/     - Symbol registry operations
    constitution/ - Governance operations
    proposals/   - Autonomy workflow
    project/     - Project lifecycle
    dev/         - Developer workflows
    admin/       - System administration

Governed by: .intent/rules/cli/interface_design.json
"""

from __future__ import annotations


__all__ = []
