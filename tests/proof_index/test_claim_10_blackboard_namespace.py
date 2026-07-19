# tests/proof_index/test_claim_10_blackboard_namespace.py
"""Proof Index claim 10: sensors cannot post outside declared type/namespace; duplicate indeterminate refused.

Standing regression check for docs/proof-index.md claim 10 (#798). Two halves:
- `post_artifact_finding` raises before any write when `artifact_type` is outside
  the worker's declared `mandate.scope.artifact_type`, or `sub_namespace` is
  outside the declared `rule_namespace`.
- `post_observation(status="indeterminate")` refuses a duplicate: it looks up an
  existing indeterminate finding for the subject and raises before `_post_entry`.

Both are pinned deterministically with a fake async session — no live DB, no
blackboard mutation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from shared.workers.blackboard_publisher import BlackboardPublisher


def _publisher(artifact_types: list[str], namespace: str) -> BlackboardPublisher:
    # Bare instance: exercise the validation branch without the DB the INSERT needs.
    pub = BlackboardPublisher.__new__(BlackboardPublisher)
    pub._worker_name = "proof-index-test"
    pub._declaration = {
        "mandate": {"scope": {"artifact_type": artifact_types, "rule_namespace": namespace}}
    }
    return pub


async def test_rejects_undeclared_artifact_type() -> None:
    pub = _publisher(["python"], "quality")
    with pytest.raises(ValueError):
        await pub.post_artifact_finding("java", "quality", "k", {})


async def test_rejects_sub_namespace_outside_declared() -> None:
    pub = _publisher(["python"], "quality")
    with pytest.raises(ValueError):
        await pub.post_artifact_finding("python", "security", "k", {})


# --- duplicate-indeterminate refusal (deterministic, no live DB) --------------


class _ExistingRow:
    """A SELECT result whose .first() reports an existing indeterminate finding."""

    def first(self) -> tuple[int]:
        return (1,)


class _FakeSession:
    def __init__(self, calls: list) -> None:
        self.calls = calls

    async def execute(self, _stmt, params=None):
        self.calls.append(params)
        return _ExistingRow()


class _FakeSessionCM:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *_exc) -> bool:
        return False


async def test_post_observation_refuses_duplicate_indeterminate() -> None:
    calls: list = []
    session = _FakeSession(calls)

    pub = BlackboardPublisher.__new__(BlackboardPublisher)
    pub._post_entry = AsyncMock()  # must never be reached on the refusal path

    with patch(
        "shared.workers.blackboard_publisher.get_session",
        return_value=_FakeSessionCM(session),
    ):
        with pytest.raises(ValueError, match="duplicate indeterminate"):
            await pub.post_observation("python::quality::x", {"k": "v"}, status="indeterminate")

    pub._post_entry.assert_not_called()
    assert calls and calls[-1]["subject"] == "python::quality::x"
