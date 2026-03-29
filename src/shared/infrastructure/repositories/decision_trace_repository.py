# src/shared/infrastructure/repositories/decision_trace_repository.py

"""
DEPRECATED: This module has been moved to comply with the Mind/Body/Will architecture.
Please import from `body.infrastructure.repositories.decision_trace_repository` instead.
"""

from __future__ import annotations

import warnings


warnings.warn(
    "shared.infrastructure.repositories.decision_trace_repository is deprecated. "
    "Import from body.infrastructure.repositories.decision_trace_repository instead.",
    DeprecationWarning,
    stacklevel=2,
)

from body.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)


__all__ = ["DecisionTraceRepository"]
