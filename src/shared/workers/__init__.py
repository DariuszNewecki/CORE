# src/shared/workers/__init__.py
"""Shared Worker infrastructure — base class and constitutional machinery."""

from __future__ import annotations

from .base import Worker, WorkerConfigurationError, WorkerRegistrationError


__all__ = ["Worker", "WorkerConfigurationError", "WorkerRegistrationError"]
