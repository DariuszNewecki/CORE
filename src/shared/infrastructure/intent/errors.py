# src/shared/infrastructure/intent/errors.py

"""Provides functionality for the errors module."""

from __future__ import annotations


# src/shared/infrastructure/intent/errors.py


# ID: 8049b8d6-25eb-44ad-af39-585ba9b73571
class GovernanceError(RuntimeError):
    """Raised when an intent artifact violates constitutional or structural rules."""
