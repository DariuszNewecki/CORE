# tests/body/services/blackboard_service/test_retired_rule_sweep.py

"""Targeting predicate for the #657 retired-rule sweep.

The sweep auto-resolves findings whose rule id left the registry. The
safety-critical part is *which* subjects it targets — it must catch
rename-orphans (real audit-violation findings citing a dead rule id) and never
touch worker observations or live-rule findings. `_retired_rule_in_subject` is
that predicate, extracted pure for these tests.
"""

from __future__ import annotations

import pytest

from body.services.blackboard_service.blackboard_service import (
    BlackboardService,
    _retired_rule_in_subject,
)


# Live registry the sweep would see: 'architecture' namespace is governed and
# contains the renamed-TO rule; the renamed-FROM id is gone.
_KNOWN_RULES = {
    "architecture.namespace.no_direct_protected_access",
    "purity.no_orphan_files",
}
_KNOWN_NAMESPACES = {"architecture", "purity"}


def _check(subject: str) -> str | None:
    return _retired_rule_in_subject(subject, _KNOWN_RULES, _KNOWN_NAMESPACES)


def test_rename_orphan_is_targeted():
    """The #490 rename-orphan (dead rule id, governed namespace) is caught."""
    subj = (
        "python::architecture.intent.non_gateway_no_direct_resolution::"
        "src/mind/logic/engines/artifact_gate.py"
    )
    assert _check(subj) == "architecture.intent.non_gateway_no_direct_resolution"


def test_live_rule_finding_is_left_alone():
    """A finding whose rule is still in the registry is NOT targeted."""
    assert _check("python::purity.no_orphan_files::src/x.py") is None


def test_worker_observation_two_segments_skipped():
    """`governance.edge5.orphan_sha::<uuid>` (2 segments, bare identity) skipped."""
    assert (
        _check("governance.edge5.orphan_sha::0b359369-00a4-43fa-bea6-f8ea8bbf5f2c")
        is None
    )


def test_telemetry_subject_skipped():
    """`loop_hold.sample::x` telemetry is structurally excluded."""
    assert _check("loop_hold.sample::worker_a") is None


def test_ungoverned_namespace_skipped():
    """A dead rule id whose namespace isn't governed at all is left alone
    (conservative — avoids touching findings outside the rule system)."""
    assert _check("python::madeup.namespace.some_rule::src/x.py") is None


def test_non_dotted_rule_segment_skipped():
    """A 3-segment subject whose middle isn't a dotted rule id is skipped."""
    assert _check("python::notarule::src/x.py") is None


@pytest.mark.asyncio
async def test_sweep_fail_closed_on_empty_registry():
    """An empty rule registry (failed load) must no-op, never touching the DB —
    otherwise the sweep would mass-resolve every finding."""
    out = await BlackboardService().resolve_findings_with_retired_rules(
        known_rule_ids=set(), known_namespaces=set()
    )
    assert out == {"resolved": 0, "retired_rules": [], "scanned": 0, "skipped": True}
