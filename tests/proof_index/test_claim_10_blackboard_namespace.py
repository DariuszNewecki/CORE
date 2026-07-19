# tests/proof_index/test_claim_10_blackboard_namespace.py
"""Proof Index claim 10: sensors cannot post outside their declared artifact type / namespace.

Standing regression check for docs/proof-index.md claim 10 (#798). Pins the
pre-INSERT validation in `BlackboardPublisher.post_artifact_finding`: an
`artifact_type` outside the worker's declared `mandate.scope.artifact_type`, or a
`sub_namespace` outside the declared `rule_namespace`, raises before any write.

Scope note: the claim's duplicate-`indeterminate`-refusal half (`post_observation`)
needs a live DB query and is covered by attestation, not this thin unit test.
"""

from __future__ import annotations

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
