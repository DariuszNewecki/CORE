# src/will/workers/test_remediator/__init__.py
"""
TestRemediator package.

Split from will/workers/test_remediator.py to satisfy modularity.needs_split.
Re-exports TestRemediatorWorker for backward compatibility.
"""

from .worker import TestRemediatorWorker


__all__ = ["TestRemediatorWorker"]
