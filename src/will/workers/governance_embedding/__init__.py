# src/will/workers/governance_embedding/__init__.py
"""GovernanceEmbedderWorker package per ADR-073 D4."""

from __future__ import annotations

from .governance_embedder_worker import GovernanceEmbedderWorker, logger


__all__ = ["GovernanceEmbedderWorker", "logger"]
