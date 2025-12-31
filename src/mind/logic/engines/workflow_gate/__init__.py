# src/mind/logic/engines/workflow_gate/__init__.py

"""
Workflow Gate Engine - Modular quality gate verification.

Architecture:
- engine.py: Main orchestrator (dispatches to checks)
- base_check.py: Abstract base class for all checks
- checks/: Individual check implementations (one per file)

Adding a new check:
1. Create checks/my_check.py inheriting from WorkflowCheck
2. Add to checks/__init__.py exports
3. Add instance to engine.py's __init__ list
"""

from __future__ import annotations

from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


__all__ = ["WorkflowGateEngine"]
