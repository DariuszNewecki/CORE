# tests/will/agents/test_resource_selector.py
"""Unit tests for ResourceSelector's base capability-matching path.

ResourceSelector is a pure stateless class -- no DB or fixtures needed,
synthetic CognitiveRole/LlmResource objects are passed directly. This
file fills a pre-existing coverage gap (per #821 Unit 3 recon): only
select_resources_for_role's high_reasoning variant had a test file
(test_resource_selector_high_reasoning.py); _is_qualified and the
singular select_resource_for_role's base capability-matching path had
none. Relevant here because Unit 3 authors the provided_capabilities
values this selector matches against.
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
    name: str, cost: int = 1, caps: list[str] | None = None, locality: str = "local"
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


# ── _is_qualified ───────────────────────────────────────────────────────────


def test_is_qualified_exact_capability_match() -> None:
    role = _role("Coder", caps=["code_generation"])
    resource = _resource("r1", caps=["code_generation"])
    assert ResourceSelector._is_qualified(resource, role) is True


def test_is_qualified_resource_has_superset_of_capabilities() -> None:
    role = _role("Coder", caps=["code_generation"])
    resource = _resource("r1", caps=["code_generation", "reasoning", "planning"])
    assert ResourceSelector._is_qualified(resource, role) is True


def test_is_qualified_missing_a_required_capability() -> None:
    role = _role("Coder", caps=["code_generation", "reasoning"])
    resource = _resource("r1", caps=["code_generation"])
    assert ResourceSelector._is_qualified(resource, role) is False


def test_is_qualified_role_requires_nothing_always_qualifies() -> None:
    role = _role("Vectorizer", caps=[])
    resource = _resource("r1", caps=[])
    assert ResourceSelector._is_qualified(resource, role) is True


def test_is_qualified_handles_json_string_capability_columns() -> None:
    """Defensive coercion: a raw JSON-string return from the driver must
    still compare correctly against a plain-list column."""
    role = CognitiveRole()
    role.role = "Coder"
    role.required_capabilities = '["code_generation"]'
    resource = LlmResource()
    resource.name = "r1"
    resource.provided_capabilities = '["code_generation", "reasoning"]'
    assert ResourceSelector._is_qualified(resource, role) is True


# ── select_resource_for_role (singular, base path) ──────────────────────────


def test_select_resource_for_role_picks_lowest_cost_among_qualified() -> None:
    role = _role("Coder", caps=["code_generation"])
    cheap = _resource("cheap", cost=1, caps=["code_generation"])
    expensive = _resource("expensive", cost=5, caps=["code_generation"])
    result = ResourceSelector.select_resource_for_role(
        "Coder", [role], [expensive, cheap], system_operating_mode="local_only"
    )
    assert result is not None
    assert result.name == "cheap"


def test_select_resource_for_role_excludes_unqualified_resources() -> None:
    role = _role("Coder", caps=["code_generation"])
    unqualified = _resource("unqualified", cost=1, caps=["reasoning"])
    qualified = _resource("qualified", cost=5, caps=["code_generation"])
    result = ResourceSelector.select_resource_for_role(
        "Coder", [role], [unqualified, qualified], system_operating_mode="local_only"
    )
    assert result is not None
    assert result.name == "qualified"


def test_select_resource_for_role_unknown_role_returns_none() -> None:
    role = _role("Coder", caps=[])
    result = ResourceSelector.select_resource_for_role(
        "NonExistentRole",
        [role],
        [_resource("r1")],
        system_operating_mode="local_only",
    )
    assert result is None


def test_select_resource_for_role_no_qualified_resources_returns_none() -> None:
    role = _role("Coder", caps=["code_generation"])
    resource = _resource("r1", caps=["reasoning"])
    result = ResourceSelector.select_resource_for_role(
        "Coder", [role], [resource], system_operating_mode="local_only"
    )
    assert result is None


def test_select_resource_for_role_no_resources_match_locality_returns_none() -> None:
    role = _role("Coder", caps=[])
    remote_only_resource = _resource("r1", locality="remote")
    result = ResourceSelector.select_resource_for_role(
        "Coder", [role], [remote_only_resource], system_operating_mode="local_only"
    )
    assert result is None


def test_select_resource_for_role_honors_active_assignment_override() -> None:
    """An explicit assignment is honored even though a cheaper qualified
    resource exists -- assignment is a deliberate governor override."""
    role = _role("Coder", caps=["code_generation"])
    assigned = _resource("assigned", cost=5, caps=["code_generation"])
    cheaper = _resource("cheaper", cost=1, caps=["code_generation"])
    assignments = [_assignment("Coder", "assigned")]
    result = ResourceSelector.select_resource_for_role(
        "Coder",
        [role],
        [assigned, cheaper],
        assignments=assignments,
        system_operating_mode="local_only",
    )
    assert result is not None
    assert result.name == "assigned"
