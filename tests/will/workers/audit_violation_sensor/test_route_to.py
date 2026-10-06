# tests/will/workers/audit_violation_sensor/test_route_to.py
"""Routing marker for architectural-judgment findings (ADR-095 D4, #943).

The sensor marks these findings ``route_to: principal.governor``. The name
``resolution_authority`` is reserved for payload.resolution, the closure
stamp that re-arms remediation caps, so the routing marker must not use it.
"""

from __future__ import annotations

import pytest

from will.audit_violation.routing import (
    _ARCHITECTURAL_JUDGMENT_RULES,
    _route_to,
)


@pytest.mark.parametrize("rule_id", sorted(_ARCHITECTURAL_JUDGMENT_RULES))
def test_architectural_judgment_rules_route_to_governor(rule_id: str) -> None:
    assert _route_to(rule_id) == "principal.governor"


def test_other_rules_are_not_routed() -> None:
    assert _route_to("architecture.channels.logic_logger_only") is None


def test_sensor_never_writes_top_level_resolution_authority() -> None:
    import inspect

    import will.workers.audit_violation_sensor as sensor_module

    source = inspect.getsource(sensor_module)
    assert 'payload["resolution_authority"]' not in source
    assert 'payload["route_to"]' in source
