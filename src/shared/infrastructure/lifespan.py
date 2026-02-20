# src/shared/infrastructure/lifespan.py

"""
DEPRECATED: This module has been moved to comply with the Mind/Body/Will architecture.
Please import from `body.infrastructure.lifespan` instead.
"""

from __future__ import annotations

import warnings


warnings.warn(
    "shared.infrastructure.lifespan is deprecated. Import from body.infrastructure.lifespan instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for any lingering external dependencies that haven't been updated yet
from body.infrastructure.lifespan import core_lifespan


__all__ = ["core_lifespan"]
