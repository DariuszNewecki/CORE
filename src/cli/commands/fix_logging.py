# src/cli/commands/fix_logging.py
"""
DEPRECATED — moved to body/self_healing/logging_service.py under ADR-050.

This module retains a re-export shim so existing in-CLI imports continue to
work during the CLI migration epic. Once all callers have been migrated to
the body location, this file should be removed.

The original AST-based logging fixer (LoggingFixer, LoggingTransformer, run_fix)
now lives at:

    body.self_healing.logging_service
"""

from __future__ import annotations

from body.self_healing.logging_service import (
    LoggingFixer,
    LoggingTransformer,
    run_fix,
)


__all__ = ["LoggingFixer", "LoggingTransformer", "run_fix"]
