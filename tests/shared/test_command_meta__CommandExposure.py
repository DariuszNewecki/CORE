# tests/shared/test_command_meta__CommandExposure.py
"""Tests for CommandExposure enum and the exposure field on CommandMeta (ADR-110 D5)."""

from __future__ import annotations

import pytest

from shared.cli.command_meta import (
    CommandBehavior,
    CommandExposure,
    CommandLayer,
    CommandMeta,
    command_meta,
    get_command_meta,
    infer_metadata_from_function,
)


# ── Enum contract ──────────────────────────────────────────────────────────────


# ID: b9e3a7d1-5c4f-4e2a-9b8d-3f6c1e0a4d72
def test_command_exposure_values() -> None:
    """Enum must have exactly two members with the expected string values."""
    assert CommandExposure.USER_FACING.value == "user-facing"
    assert CommandExposure.GOVERNOR_ONLY.value == "governor-only"
    assert set(CommandExposure) == {CommandExposure.USER_FACING, CommandExposure.GOVERNOR_ONLY}


# ── CommandMeta field enforcement ─────────────────────────────────────────────


# ID: 4a8f2e6b-1d3c-4b9a-8e7f-2c5d0a3b6e91
def test_command_meta_exposure_is_required() -> None:
    """CommandMeta must reject construction when exposure is missing."""
    with pytest.raises(TypeError, match="exposure"):
        CommandMeta(
            canonical_name="test.cmd",
            behavior=CommandBehavior.READ,
            layer=CommandLayer.BODY,
            summary="A test command",
        )


# ID: 7d2b5f3a-9e4c-4d8b-a1f6-3c7e0b2d4f85
def test_command_meta_accepts_user_facing() -> None:
    """CommandMeta must store USER_FACING exposure correctly."""
    meta = CommandMeta(
        canonical_name="inspect.status",
        behavior=CommandBehavior.READ,
        layer=CommandLayer.BODY,
        exposure=CommandExposure.USER_FACING,
        summary="Show system status",
    )
    assert meta.exposure is CommandExposure.USER_FACING


# ID: c1e4d8a6-2f7b-4c3e-b5a9-8d1f0c2e5b37
def test_command_meta_accepts_governor_only() -> None:
    """CommandMeta must store GOVERNOR_ONLY exposure correctly."""
    meta = CommandMeta(
        canonical_name="admin.sync",
        behavior=CommandBehavior.MUTATE,
        layer=CommandLayer.WILL,
        exposure=CommandExposure.GOVERNOR_ONLY,
        summary="Sync the database",
        dangerous=True,
    )
    assert meta.exposure is CommandExposure.GOVERNOR_ONLY


# ── @command_meta decorator ────────────────────────────────────────────────────


# ID: e5c2b9d4-7a3f-4e1b-8c6d-0f4a2e7b3c58
def test_command_meta_decorator_sets_exposure() -> None:
    """@command_meta decorator must propagate exposure to __command_meta__."""

    @command_meta(
        canonical_name="inspect.patterns",
        behavior=CommandBehavior.READ,
        layer=CommandLayer.BODY,
        exposure=CommandExposure.USER_FACING,
        summary="Inspect code patterns",
    )
    def fake_cmd() -> None:
        pass

    retrieved = get_command_meta(fake_cmd)
    assert retrieved is not None
    assert retrieved.exposure is CommandExposure.USER_FACING


# ── infer_metadata_from_function fallback ─────────────────────────────────────


# ID: 3f6d1a9e-8b2c-4a7d-b4e5-6c0f3d1a8b25
def test_infer_metadata_defaults_to_governor_only() -> None:
    """Commands without explicit @command_meta must infer GOVERNOR_ONLY (fail-safe)."""

    def inferred_cmd() -> None:
        """Show something."""

    meta = infer_metadata_from_function(inferred_cmd, "inferred-cmd")
    assert meta.exposure is CommandExposure.GOVERNOR_ONLY
