# src/body/workers/violation_remediator/__init__.py
"""
ViolationRemediator package.

Split from body/workers/violation_remediator.py.
Re-exports ViolationRemediator for backward compatibility.
"""

from .worker import ViolationRemediator


__all__ = ["ViolationRemediator"]
