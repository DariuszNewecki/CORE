# src/shared/infrastructure/repo_code.py
"""
The seam through which layers that must not run repository code ask for it
to be run (ADR-132 D10.10).

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination) -- holds one
registered callable; runs nothing itself.

Mind's workflow gate checks that the test suite still collects. Collecting
imports every test module, which is running repository code, and Mind may
neither run code nor import Body. Body registers its sandbox collector here
when it is imported (body.sandbox.repo_tests); Mind asks for it. Nothing
registered means the check cannot run: callers report it unavailable, never
as a pass.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
# ID: 0f4e174a-f8d0-480d-a3c7-0172229697a9
class CollectOutcome:
    """What a sandboxed collection found. ``status``: passed (collected
    cleanly), failed (collection errors, listed in ``output``), or not_run /
    error / timeout (nothing known)."""

    status: str
    output: str = ""
    reason: str = ""


TestCollector = Callable[[Path, int], Awaitable[CollectOutcome]]

_collector: TestCollector | None = None


# ID: 459cc332-db66-408f-b4d7-44615724de21
def register_test_collector(collector: TestCollector) -> None:
    """Install the collector (Body's sandbox runner)."""
    global _collector
    _collector = collector


# ID: f44ec65e-2f07-43f5-b488-00e19a4fa5dd
def get_test_collector() -> TestCollector | None:
    """The registered collector, or None when none is installed."""
    return _collector
