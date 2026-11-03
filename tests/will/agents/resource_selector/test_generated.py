from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


# ID: 81993168-25fc-4b2b-9585-74bcdc3a6023
def test_ResourceSelector():
    from will.agents.resource_selector import ResourceSelector

    role = SimpleNamespace(
        role="coder",
        required_capabilities='["code"]',
    )
    roles = [role]

    cheap_local = SimpleNamespace(
        name="cheap-local",
        locality="local",
        provided_capabilities='["code"]',
        performance_metadata='{"cost_rating": 1}',
    )
    expensive_local = SimpleNamespace(
        name="expensive-local",
        locality="local",
        provided_capabilities='["code"]',
        performance_metadata='{"cost_rating": 5}',
    )
    remote = SimpleNamespace(
        name="remote",
        locality="remote",
        provided_capabilities='["code"]',
        performance_metadata='{"cost_rating": 1}',
    )

    resources = [expensive_local, cheap_local, remote]

    with patch(
        "will.agents.resource_selector._primary_assignment",
        return_value=None,
    ):
        result = ResourceSelector.select_resource_for_role(
            "coder",
            roles,
            resources,
            assignments=None,
            system_operating_mode="local_only",
        )
        assert result is cheap_local

        plural = ResourceSelector.select_resources_for_role(
            "coder",
            roles,
            resources,
            assignments=None,
            system_operating_mode="local_only",
        )
        assert plural == [cheap_local, expensive_local]

        escalation = ResourceSelector.select_resources_for_role(
            "coder",
            roles,
            resources,
            assignments=None,
            system_operating_mode="local_only",
            high_reasoning=True,
        )
        assert escalation == [expensive_local, cheap_local]

        assert (
            ResourceSelector.select_resource_for_role(
                "missing-role", roles, resources, system_operating_mode="local_only"
            )
            is None
        )


from unittest.mock import MagicMock

from will.agents.resource_selector import ResourceSelector


# ID: 73e9b764-f735-4d74-a0cc-3816bee72c81
def test_ResourceSelector_select_resources_for_role():
    role = MagicMock()
    role.role = "engineer"

    low = MagicMock()
    low.name = "low-cost"
    low.cost_rating = 1

    mid = MagicMock()
    mid.name = "mid-cost"
    mid.cost_rating = 2

    with (
        patch.object(
            ResourceSelector,
            "_filter_by_locality",
            side_effect=lambda resources, mode, role_name: resources,
        ),
        patch.object(
            ResourceSelector,
            "_is_qualified",
            return_value=True,
        ),
        patch.object(
            ResourceSelector,
            "_score_resource",
            side_effect=lambda r: r.cost_rating,
        ),
        patch(
            "will.agents.resource_selector._primary_assignment",
            return_value=None,
        ),
    ):
        result = ResourceSelector.select_resources_for_role(
            "engineer",
            [role],
            [mid, low],
            assignments=None,
            system_operating_mode="normal",
        )

    assert result == [low, mid]




from will.agents import resource_selector


# ID: a69680ef-eb02-4fcf-a1c0-749a51ac198e
def test_ResourceSelector_select_resource_for_role():
    select_resource_for_role = getattr(
        resource_selector, "select_resource_for_role", None
    )
    if select_resource_for_role is None:
        select_resource_for_role = ResourceSelector.select_resource_for_role

    role = MagicMock()
    role.role = "architect"

    resource = MagicMock()
    resource.name = "gpt-4"

    with (
        patch.object(
            ResourceSelector,
            "_filter_by_locality",
            return_value=[resource],
        ),
        patch.object(
            resource_selector,
            "_primary_assignment",
            return_value=None,
            create=True,
        ),
        patch.object(
            ResourceSelector,
            "_is_qualified",
            return_value=True,
        ),
        patch.object(
            ResourceSelector,
            "_score_resource",
            return_value=0,
        ),
    ):
        result = select_resource_for_role(
            "architect",
            [role],
            [resource],
            assignments=None,
            system_operating_mode="local",
        )

    assert result is resource
