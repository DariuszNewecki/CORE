"""Tests for AuditViolationSensor.

2026-06-07 (#572 Cat B batch 19): the autogen vintage of this file was
entirely speculative — it defined a local ``class AuditViolationSensor:
pass`` placeholder (instead of importing the real worker), wired up
mock factory functions that returned classes with no actual methods,
asserted on call_count attributes that would have raised AttributeError
on the placeholder mocks, and used MagicMock without importing it
(NameError on the only test). The file was effectively dead — nothing
referenced the real ``will.workers.audit_violation_sensor`` symbol.

Replaced with a minimal smoke test against the real class. The worker
takes ``(core_context, declaration_name, rule_namespace,
dry_run=True)`` and inherits from the Worker base. A deeper behavioural
test belongs in an integration suite where the blackboard / consequence
log services and a real session provider are available; the smoke test
pins the import surface and the constructor signature without taking
on integration-level setup.
"""

from __future__ import annotations

from unittest.mock import Mock

from will.workers.audit_violation_sensor import AuditViolationSensor


def test_audit_violation_sensor_constructs_with_required_args():
    """AuditViolationSensor.__init__ requires
    (core_context, declaration_name, rule_namespace) — the optional
    ``dry_run`` defaults to True so destructive runs are opt-in.

    ``declaration_name`` is looked up against
    ``.intent/workers/<name>.yaml`` at construction time, so it must be
    a name that has a real declaration on disk. ``audit_violation_sensor``
    is the worker's own canonical name and is the only declaration
    guaranteed to exist for this worker class."""
    ctx = Mock()
    sensor = AuditViolationSensor(
        core_context=ctx,
        declaration_name="audit_violation_sensor",
        rule_namespace="example_ns",
    )
    assert sensor.declaration_name == "audit_violation_sensor"
