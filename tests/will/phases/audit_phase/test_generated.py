from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.phases.audit_phase import AuditPhase


# ID: d6f41fc3-b765-42d9-b57f-71b72fad3d0b
async def test_AuditPhase_execute() -> None:
    core_context = MagicMock()

    with (
        patch("will.phases.audit_phase.CanaryValidationPhase") as canary_cls,
        patch("will.phases.audit_phase.SandboxValidationPhase") as sandbox_cls,
        patch("will.phases.audit_phase.StyleCheckPhase") as style_cls,
    ):
        canary_instance = MagicMock()
        sandbox_instance = MagicMock()
        style_instance = MagicMock()
        canary_cls.return_value = canary_instance
        sandbox_cls.return_value = sandbox_instance
        style_cls.return_value = style_instance

        phase = AuditPhase(core_context)

        canary_result = MagicMock()
        canary_result.ok = True
        canary_result.data = {"canary": "ok"}
        canary_result.error = None
        canary_instance.execute = AsyncMock(return_value=canary_result)

        style_result = MagicMock()
        style_result.ok = True
        style_result.data = {"style": "ok"}
        style_result.error = None
        style_instance.execute = AsyncMock(return_value=style_result)

        # Use default routing (refactor_modularity -> canary_validation + style_check)
        context = MagicMock()
        context.workflow_type = "refactor_modularity"
        context.results = {}

        result = await phase.execute(context)

    assert result.ok is True
    assert result.name == "audit"
    assert result.data["audit_result_explicit"] is True
    assert result.data["rule_evaluation_complete"] is True
    assert result.data["advisory_failures"] == []
    assert result.data["canary_validation"] == {"canary": "ok"}
    assert result.data["style_check"] == {"style": "ok"}
    assert context.results["canary_validation"] == {"canary": "ok"}
    assert context.results["style_check"] == {"style": "ok"}
    canary_instance.execute.assert_awaited_once_with(context)
    style_instance.execute.assert_awaited_once_with(context)
