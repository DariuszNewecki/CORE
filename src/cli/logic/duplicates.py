# src/cli/logic/duplicates.py
"""
DEPRECATED — moved to body/self_healing/duplicates_service.py under ADR-050.

This module retains a re-export shim so existing in-CLI imports continue to
work during the CLI migration epic. Once all callers have been migrated to
the body location, this file should be removed.

The duplicate-code analysis logic (inspect_duplicates_async) now lives at:

    body.self_healing.duplicates_service
"""

from __future__ import annotations

from body.self_healing.duplicates_service import inspect_duplicates_async


__all__ = ["inspect_duplicates_async"]
