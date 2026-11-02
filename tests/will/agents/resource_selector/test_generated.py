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
