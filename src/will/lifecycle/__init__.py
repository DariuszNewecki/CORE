# src/will/lifecycle/__init__.py

"""
Will-layer lifecycle facades — sibling to body.project_lifecycle.

The API layer cannot import body.* directly; this package exposes
thin Will-layer wrappers around body.project_lifecycle so the API
has a constitutional path to the underlying operations. Same pattern
as will/governance/audit_runner.py for body.governance.
"""

from __future__ import annotations
