# src/will/governance/__init__.py

"""
Will-layer governance facades.

This package exposes thin facades the API layer can import without
reaching into mind.* or shared.infrastructure.* directly. ADR-054
Phase 1 introduces the first such facade: run_and_persist_audit,
which wraps mind.enforcement.audit.run_audit_workflow with persistence
into core.audit_run_resources.
"""

from __future__ import annotations
