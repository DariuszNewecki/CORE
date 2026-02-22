# src/body/cli/logic/interactive_test/workflow.py
# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c

"""
Interactive test generation workflow orchestration.

Coordinates the 5-step workflow and handles state transitions.

HEALED (V2.3.0):
- Signature Alignment: Matches CoderAgent V2.6+ constructor exactly.
- Inversion of Control: Injects 'action_executor' as the mandatory 'executor'.
- Service Robustness: Added JIT wake-up for Cognitive and Auditor services if None.
- Safety: Added checks for empty decision lists to prevent IndexError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from body.cli.logic.interactive_test.session import InteractiveSession
from body.cli.logic.interactive_test.steps import (
    step_audit,
    step_auto_heal,
    step_canary,
    step_execute,
    step_generate_code,
)
from body.cli.logic.interactive_test.ui import (
    show_cancellation,
    show_header,
    show_success_message,
)
from body.services.service_registry import _ServiceLoader
from shared.context import CoreContext
from shared.logger import getLogger


if TYPE_CHECKING:
    from will.agents.coder_agent import CoderAgent


logger = getLogger(__name__)


# ID: e0f08996-0583-4a13-b367-8bea5df6ab8b
async def run_interactive_workflow(
    target_file: str,
    core_context: CoreContext,
) -> bool:
    """
    Run the complete interactive test generation workflow.

    Args:
        target_file: Module to generate tests for
        core_context: Core context with services

    Returns:
        True if successful, False if user cancelled
    """
    session = InteractiveSession(target_file, core_context.git_service.repo_path)

    try:
        show_header(target_file)
        coder_agent = await _initialize_services(core_context)

        success, generated_code = await step_generate_code(
            session, target_file, coder_agent
        )
        if not success:
            show_cancellation()
            return False

        success, healed_code = await step_auto_heal(session, generated_code)
        if not success:
            show_cancellation()
            return False

        if session.decisions and session.decisions[-1]["choice"] == "s":
            test_path = target_file.replace("src/", "tests/").replace(
                ".py", "/test_generated.py"
            )
            success = await step_execute(session, healed_code, target_file)
            if success:
                show_success_message(test_path)
                return True
            else:
                show_cancellation()
                return False

        success, _audit_report = await step_audit(session, healed_code)
        if not success:
            show_cancellation()
            return False

        if session.decisions and session.decisions[-1]["choice"] == "s":
            test_path = target_file.replace("src/", "tests/").replace(
                ".py", "/test_generated.py"
            )
            success = await step_execute(session, healed_code, target_file)
            if success:
                show_success_message(test_path)
                return True
            else:
                show_cancellation()
                return False

        success, _ran_canary = await step_canary(session)
        if not success:
            show_cancellation()
            return False

        final_code = healed_code
        test_path = target_file.replace("src/", "tests/").replace(
            ".py", "/test_generated.py"
        )

        success = await step_execute(session, final_code, target_file)
        if success:
            show_success_message(test_path)
            return True
        else:
            show_cancellation()
            return False

    finally:
        session.finalize()


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
async def _initialize_services(core_context: CoreContext) -> CoderAgent:
    """
    Initialize required services for workflow.

    CONSTITUTIONAL COMPLIANCE:
    - Uses existing services from CoreContext (DI principle).
    - JIT Service Activation: Automatically wakes up services from registry if missing.
    """
    cognitive_service = core_context.cognitive_service
    if cognitive_service is None:
        cognitive_service = await core_context.registry.get_cognitive_service()

    auditor_context = core_context.auditor_context
    if auditor_context is None:
        auditor_context = await core_context.registry.get_auditor_context()

    executor = core_context.action_executor

    PromptPipeline = _ServiceLoader.import_class(
        "will.orchestration.prompt_pipeline.PromptPipeline"
    )
    prompt_pipeline = PromptPipeline(core_context.git_service.repo_path)

    context_service = None
    try:
        context_service = core_context.context_service
    except Exception as e:
        logger.debug("ContextService not available: %s", e)

    CoderAgent = _ServiceLoader.import_class("will.agents.coder_agent.CoderAgent")
    coder_agent = CoderAgent(
        cognitive_service=cognitive_service,
        executor=executor,
        prompt_pipeline=prompt_pipeline,
        auditor_context=auditor_context,
        repo_root=core_context.git_service.repo_path,
        context_service=context_service,
    )

    return coder_agent
