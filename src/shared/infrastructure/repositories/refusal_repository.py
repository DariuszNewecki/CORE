# src/shared/infrastructure/repositories/refusal_repository.py

"""
DEPRECATED: This module has been moved to comply with the Mind/Body/Will architecture.
Please import from `body.infrastructure.repositories.refusal_repository` instead.
"""

from __future__ import annotations

import warnings


warnings.warn(
    "shared.infrastructure.repositories.refusal_repository is deprecated. "
    "Import from body.infrastructure.repositories.refusal_repository instead.",
    DeprecationWarning,
    stacklevel=2,
)

from body.infrastructure.repositories.refusal_repository import RefusalRepository


__all__ = ["RefusalRepository"]
