"""ADR-025: CoreContext.context_builder factory + property + cache wiring.

Pure unit test of the wiring contract — does NOT exercise
ArchitecturalContextBuilder constructibility (that's a separate concern
from CoreContext wiring). Stub factory returns a sentinel; the test
asserts the property routes through the factory exactly once and caches
the result.
"""

from __future__ import annotations

import pytest

from shared.context import CoreContext


# ID: cc73b8cd-ee95-417e-b7a7-5f5179968369
def test_context_builder_raises_when_factory_not_configured() -> None:
    """First read with no factory wired surfaces a clear RuntimeError."""
    context = CoreContext(registry=object(), git_service=object())

    with pytest.raises(RuntimeError, match="ArchitecturalContextBuilder factory"):
        _ = context.context_builder


# ID: c32ccf9b-7701-4a4c-932d-b13085167336
def test_context_builder_routes_through_factory_and_caches() -> None:
    """Factory is invoked exactly once; subsequent reads return the cached instance."""
    sentinel = object()
    call_count = 0

    def factory():
        nonlocal call_count
        call_count += 1
        return sentinel

    context = CoreContext(
        registry=object(), git_service=object(), context_builder_factory=factory
    )

    first = context.context_builder
    second = context.context_builder

    assert first is sentinel
    assert second is sentinel
    assert call_count == 1
