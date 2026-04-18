# src/shared/infrastructure/specs/__init__.py
"""Specs layer infrastructure — read-only access to .specs/ human intent documents."""

from __future__ import annotations

from .specs_repository import SpecsRepository, get_specs_repository


__all__ = ["SpecsRepository", "get_specs_repository"]
