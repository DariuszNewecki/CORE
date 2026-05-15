# src/cli/logic/body_contracts_checker.py
"""
DEPRECATED — moved to body/governance/body_contracts_service.py under ADR-050.

This module retains a re-export shim so existing in-CLI imports continue to
work during the CLI migration epic. Once all callers have been migrated to
the body location, this file should be removed.

The original Body Contracts Checker (check_body_contracts, Violation, and
internal helpers) now lives at:

    body.governance.body_contracts_service
"""

from __future__ import annotations

from body.governance.body_contracts_service import (
    Violation,
    check_body_contracts,
)


__all__ = ["Violation", "check_body_contracts"]
