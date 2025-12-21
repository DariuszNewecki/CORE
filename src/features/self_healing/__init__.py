# src/features/self_healing/__init__.py
"""Self-healing capabilities for CORE."""

from __future__ import annotations

from .memory_cleanup_service import MemoryCleanupService


__all__ = [
    "MemoryCleanupService",
]
