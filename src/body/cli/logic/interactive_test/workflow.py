# src/body/cli/logic/interactive_test/workflow.py

"""
Interactive test generation workflow orchestration.

Coordinates the 5-step workflow and handles state transitions.

Constitutional Compliance:
- Single Responsibility: Only workflow coordination
- Clear flow: Delegates to step handlers, UI shows results
- Error handling: Proper cleanup and logging
- DI Pattern: Uses services from CoreContext (no direct instantiation)
- Registry Pattern: Respects singleton services via registry
"""

from __future__ import annotations

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
from shared.context import CoreContext
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
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
        # Header
        show_header(target_file)

        # Initialize services (uses CoreContext services, no direct instantiation)
        coder_agent = await _initialize_services(core_context)

        # ====================================================================
        # STEP 1: GENERATE CODE
        # ====================================================================
        success, generated_code = await step_generate_code(
            session, target_file, coder_agent
        )
        if not success:
            show_cancellation()
            return False

        # ====================================================================
        # STEP 2: AUTO-HEAL CODE
        # ====================================================================
        success, healed_code = await step_auto_heal(session, generated_code)
        if not success:
            show_cancellation()
            return False

        # Check if user skipped ahead to execute
        if session.decisions[-1]["choice"] == "s":
            # Skip to step 5
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

        # ====================================================================
        # STEP 3: CONSTITUTIONAL AUDIT
        # ====================================================================
        success, _audit_report = await step_audit(session, healed_code)
        if not success:
            show_cancellation()
            return False

        # Check if user skipped ahead to execute
        if session.decisions[-1]["choice"] == "s":
            # Skip to step 5
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

        # ====================================================================
        # STEP 4: CANARY TRIAL (Optional)
        # ====================================================================
        success, _ran_canary = await step_canary(session)
        if not success:
            show_cancellation()
            return False

        # ====================================================================
        # STEP 5: EXECUTE
        # ====================================================================
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
    - Uses existing services from CoreContext (DI principle)
    - Uses registry for service resolution (no direct instantiation)
    - Respects singleton pattern (no duplicate instances)
    - Proper property access for lazy-loaded services

    Args:
        core_context: Core context with pre-initialized services

    Returns:
        Initialized CoderAgent
    """
    # Use existing services from CoreContext (already initialized by CLI/API)
    cognitive_service = core_context.cognitive_service
    auditor_context = core_context.auditor_context

    # Create PromptPipeline (stateless utility, safe to create)
    prompt_pipeline = PromptPipeline(core_context.git_service.repo_path)

    # Get Qdrant from registry if available (respects singleton pattern)
    qdrant_service = None
    try:
        if core_context.registry:
            qdrant_service = await core_context.registry.get_qdrant_service()
            logger.info("Qdrant service available for semantic features")
    except Exception as e:
        logger.debug("Qdrant not available (optional): %s", e)

    # Get ContextService via property (triggers factory if needed)
    context_service = None
    try:
        context_service = core_context.context_service
        logger.info("ContextService available for enriched code generation")
    except Exception as e:
        logger.debug("ContextService not available: %s", e)

    # Create CoderAgent with all available services
    coder_agent = CoderAgent(
        cognitive_service=cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=auditor_context,
        repo_root=core_context.git_service.repo_path,
        qdrant_service=qdrant_service,
        context_service=context_service,
    )

    return coder_agent
