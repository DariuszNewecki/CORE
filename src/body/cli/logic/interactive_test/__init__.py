# src/body/cli/logic/interactive_test/__init__.py

"""
Interactive test generation package.

Provides step-by-step visibility and control over autonomous test generation.

Components:
- session: Session state and artifact management
- ui: Rich console UI components
- steps: Individual step handlers (generate, heal, audit, canary, execute)
- workflow: Workflow orchestration
"""

from __future__ import annotations

from body.cli.logic.interactive_test.workflow import run_interactive_workflow


# Public API
__all__ = ["run_interactive_workflow"]
