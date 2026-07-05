"""Unit tests for ResourceSelector.select_resources_for_role high_reasoning flag.

ResourceSelector is a pure stateless class, so these tests need no DB or
fixtures — they pass synthetic CognitiveRole and LlmResource objects directly.
"""

from __future__ import annotations

import json

from shared.infrastructure.database.models import (
    CognitiveRole,
    LlmResource,
    RoleResourceAssignment,
)
from will.agents.resource_selector import ResourceSelector


def _role(name: str, caps: list[str] | None = None) -> CognitiveRole:
    r = CognitiveRole()
    r.role = name
    r.required_capabilities = json.dumps(caps or [])
    return r


def _resource(
    name: str, cost: int, caps: list[str] | None = None, locality: str = "local"
) -> LlmResource:
    r = LlmResource()
    r.name = name
    r.locality = locality
    r.provided_capabilities = json.dumps(caps or [])
    r.performance_metadata = json.dumps({"cost_rating": cost})
    return r


def _assignment(role: str, resource: str, priority: int = 1) -> RoleResourceAssignment:
    a = RoleResourceAssignment()
    a.role = role
    a.resource = resource
    a.priority = priority
    a.is_active = True
    return a


ROLE = _role("Coder")
CHEAP = _resource("cheap_model", cost=1)
MID = _resource("mid_model", cost=3)
EXPERT = _resource("expert_model", cost=5)
ALL = [CHEAP, MID, EXPERT]


def test_normal_path_lowest_cost_first() -> None:
    result = ResourceSelector.select_resources_for_role(
        "Coder", [ROLE], ALL, system_operating_mode="local_only"
    )
    assert [r.name for r in result] == ["cheap_model", "mid_model", "expert_model"]


def test_high_reasoning_highest_cost_first() -> None:
    result = ResourceSelector.select_resources_for_role(
        "Coder", [ROLE], ALL, system_operating_mode="local_only", high_reasoning=True
    )
    assert [r.name for r in result] == ["expert_model", "mid_model", "cheap_model"]


def test_normal_path_assignment_at_position_zero() -> None:
    assignments = [_assignment("Coder", "mid_model")]
    result = ResourceSelector.select_resources_for_role(
        "Coder",
        [ROLE],
        ALL,
        assignments=assignments,
        system_operating_mode="local_only",
    )
    assert result[0].name == "mid_model", (
        "assigned resource must be first on normal path"
    )


def test_high_reasoning_skips_assignment_override() -> None:
    """Assignment (mid_model) must NOT be promoted when high_reasoning=True;
    the most capable resource (expert_model) must lead."""
    assignments = [_assignment("Coder", "mid_model")]
    result = ResourceSelector.select_resources_for_role(
        "Coder",
        [ROLE],
        ALL,
        assignments=assignments,
        system_operating_mode="local_only",
        high_reasoning=True,
    )
    assert result[0].name == "expert_model", (
        "high_reasoning must place highest-cost resource first regardless of assignment"
    )


def test_high_reasoning_single_resource_returns_it() -> None:
    result = ResourceSelector.select_resources_for_role(
        "Coder", [ROLE], [MID], system_operating_mode="local_only", high_reasoning=True
    )
    assert len(result) == 1
    assert result[0].name == "mid_model"


def test_high_reasoning_unknown_role_returns_empty() -> None:
    result = ResourceSelector.select_resources_for_role(
        "NonExistentRole",
        [ROLE],
        ALL,
        system_operating_mode="local_only",
        high_reasoning=True,
    )
    assert result == []


def test_high_reasoning_respects_locality_filter() -> None:
    remote_expert = _resource("remote_expert", cost=5, locality="remote")
    local_cheap = _resource("local_cheap", cost=1, locality="local")
    result = ResourceSelector.select_resources_for_role(
        "Coder",
        [ROLE],
        [remote_expert, local_cheap],
        system_operating_mode="local_only",
        high_reasoning=True,
    )
    names = [r.name for r in result]
    assert "remote_expert" not in names, (
        "locality filter must apply even with high_reasoning"
    )
    assert "local_cheap" in names
