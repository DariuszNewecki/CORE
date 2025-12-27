# src/mind/logic/engines/ast_gate.py
"""
Backward compatibility wrapper for modularized AST Gate Engine.

This file maintains the original import path while redirecting to the
new modular structure. Allows existing code to continue working without
changes while benefiting from the modularized architecture.

Original: src/mind/logic/engines/ast_gate.py (569 lines, monolithic)
New: src/mind/logic/engines/ast_gate/ (package, ~60 lines per module)
"""

from __future__ import annotations

# Re-export from modular implementation
from mind.logic.engines.ast_gate import ASTGateEngine


__all__ = ["ASTGateEngine"]
