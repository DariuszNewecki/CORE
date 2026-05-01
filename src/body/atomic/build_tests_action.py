# src/body/atomic/build_tests_action.py

"""
Atomic Build Action - Test Generation

Generates a test file for a source file using CoderAgent, then runs
auto-heal (fix.imports, fix.headers, fix.format) and IntentGuard validation.

Constitutional Alignment:
- Boundary: Uses CoreContext for repo_path (no direct settings access)
- Circularity Fix: Feature-level imports are performed inside functions.
- Remediation: Declares remediates=["test.failure", "test.missing"] so
  ViolationRemediatorWorker can close the autonomous test loop.
- Path mapping: source_file -> test_file is resolved via
  shared.infrastructure.intent.test_coverage_paths.source_to_test_path
  (governed by .intent/enforcement/config/test_coverage.yaml).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


@register_action(
    action_id="build.tests",
    description="Generate a test file for a source file using CoderAgent",
    category=ActionCategory.BUILD,
    policies=["rules/code/purity"],
    impact_level="safe",
    remediates=["test.failure", "test.missing"],
)
@atomic_action(
    action_id="build.tests",
    intent="Generate comprehensive tests for a source file via CoderAgent and auto-heal pipeline",
    impact=ActionImpact.WRITE_CODE,
    policies=["atomic_actions"],
)
# ID: 8f4a2b6c-d3e7-4019-a5b8-1c9f0e7d6a34
async def action_build_tests(
    source_file: str,
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """
    Generate a test file for source_file using CoderAgent.

    1. Map source_file to test_file path (governed by .intent/)
    2. Initialize CoderAgent (same as interactive_test workflow)
    3. Call coder_agent.generate_or_repair(task, goal)
    4. Run auto-heal: fix.imports, fix.headers, fix.format
    5. Run IntentGuard validation on generated code
    6. If write=True: create the test file via action_create_file
    7. Return ActionResult
    """
    from body.atomic.executor import ActionExecutor
    from body.atomic.file_ops import action_create_file
    from body.governance.intent_guard import get_intent_guard
    from body.services.service_registry import _ServiceLoader
    from shared.infrastructure.intent.test_coverage_paths import (
        source_to_test_path,
    )
    from shared.models.execution_models import ExecutionTask, TaskParams

    start = time.time()
    repo_root = core_context.git_service.repo_path

    # 1. Map source_file to test_file path via governed helper.
    #    src/foo/bar.py → tests/foo/bar/test_generated.py
    try:
        test_file = source_to_test_path(source_file)
    except ValueError as e:
        return ActionResult(
            action_id="build.tests",
            ok=False,
            data={"error": f"Invalid source path: {e}"},
            duration_sec=time.time() - start,
        )

    logger.info(
        "build.tests: generating tests for %s → %s",
        source_file,
        test_file,
    )

    # 2. Verify source file exists
    source_path = repo_root / source_file
    if not source_path.exists():
        return ActionResult(
            action_id="build.tests",
            ok=False,
            data={"error": f"Source file not found: {source_file}"},
            duration_sec=time.time() - start,
        )

    # 3. Initialize CoderAgent (mirrors _initialize_services in workflow.py)
    try:
        cognitive_service = core_context.cognitive_service
        if cognitive_service is None:
            cognitive_service = await core_context.registry.get_cognitive_service()

        auditor_context = core_context.auditor_context
        if auditor_context is None:
            auditor_context = await core_context.registry.get_auditor_context()

        if not hasattr(core_context, "action_executor"):
            core_context.action_executor = ActionExecutor(core_context)
        executor = core_context.action_executor

        PromptPipeline = _ServiceLoader.import_class(
            "will.orchestration.prompt_pipeline.PromptPipeline"
        )
        prompt_pipeline = PromptPipeline(repo_root)

        context_service = None
        try:
            context_service = core_context.context_service
        except Exception as e:
            logger.debug("ContextService not available via property: %s", e)

        if context_service is None:
            try:
                from shared.infrastructure.context.service import ContextService

                context_service = ContextService(
                    project_root=str(repo_root),
                    session_factory=core_context.registry.session,
                    qdrant_client=None,
                    cognitive_service=None,
                )
                logger.info(
                    "build.tests: constructed ContextService via registry JIT fallback"
                )
            except Exception as e:
                logger.warning(
                    "build.tests: failed to construct ContextService via registry: %s",
                    e,
                )

        CoderAgent = _ServiceLoader.import_class("will.agents.coder_agent.CoderAgent")
        coder_agent = CoderAgent(
            cognitive_service=cognitive_service,
            executor=executor,
            prompt_pipeline=prompt_pipeline,
            auditor_context=auditor_context,
            repo_root=repo_root,
            context_service=context_service,
        )
    except Exception as e:
        logger.error("build.tests: failed to initialize CoderAgent: %s", e)
        return ActionResult(
            action_id="build.tests",
            ok=False,
            data={"error": f"CoderAgent initialization failed: {e}"},
            duration_sec=time.time() - start,
        )

    # 4. Construct ExecutionTask and generate code.
    #    CoderAgent -> CodeGenerator._build_context_package reads
    #    task.params.file_path as target_file for ContextService.
    #    Pointing file_path at the SOURCE file (not the not-yet-existing
    #    test file) is what gives the LLM real symbols to ground tests
    #    in. The test file path is communicated via the goal string and
    #    is still the write destination in step 7 below.
    task = ExecutionTask(
        step=f"Generate comprehensive pytest tests for module {source_file}",
        action="generate",
        params=TaskParams(
            file_path=source_file,
            symbol_name=None,
        ),
        task_type="test_generation",
    )
    goal = (
        f"Generate a comprehensive pytest test module for the source "
        f"file {source_file}. The generated test module will be "
        f"written to {test_file}. Cover the public symbols of the "
        f"source module. Use only imports, classes, and functions "
        f"that exist in the provided context evidence — do not "
        f"invent symbols."
    )

    try:
        generated_code = await coder_agent.generate_or_repair(task, goal)
    except Exception as e:
        logger.error("build.tests: code generation failed: %s", e)
        return ActionResult(
            action_id="build.tests",
            ok=False,
            data={"error": f"Code generation failed: {e}", "test_file": test_file},
            duration_sec=time.time() - start,
        )

    if not generated_code or not generated_code.strip():
        return ActionResult(
            action_id="build.tests",
            ok=False,
            data={"error": "CoderAgent returned empty code", "test_file": test_file},
            duration_sec=time.time() - start,
        )

    # 5. Auto-heal: fix.imports, fix.headers, fix.format
    action_executor = ActionExecutor(core_context)
    for fix_action_id in ("fix.imports", "fix.headers", "fix.format"):
        try:
            fix_result = await action_executor.execute(fix_action_id, write=write)
            if not fix_result.ok:
                logger.warning(
                    "build.tests: %s returned ok=False: %s",
                    fix_action_id,
                    fix_result.data,
                )
        except Exception as e:
            logger.warning("build.tests: %s failed: %s", fix_action_id, e)

    # 6. IntentGuard validation
    try:
        intent_guard = get_intent_guard(repo_path=repo_root)
        validation = intent_guard.validate_generated_code(
            code=generated_code,
            pattern_id="test_file",
            component_type="test",
            target_path=test_file,
        )
        if not validation.ok:
            logger.warning(
                "build.tests: IntentGuard flagged generated code: %s",
                validation.data if hasattr(validation, "data") else validation,
            )
    except Exception as e:
        logger.warning("build.tests: IntentGuard check failed: %s", e)

    # 7. Write file if requested
    if write:
        try:
            create_result = await action_create_file(
                test_file, generated_code, core_context, write=True
            )
            if not create_result.ok:
                return ActionResult(
                    action_id="build.tests",
                    ok=False,
                    data={
                        "error": "Failed to write test file",
                        "details": create_result.data,
                        "test_file": test_file,
                    },
                    duration_sec=time.time() - start,
                )
        except Exception as e:
            return ActionResult(
                action_id="build.tests",
                ok=False,
                data={"error": f"File write failed: {e}", "test_file": test_file},
                duration_sec=time.time() - start,
            )

    return ActionResult(
        action_id="build.tests",
        ok=True,
        data={
            "source_file": source_file,
            "test_file": test_file,
            "write": write,
        },
        duration_sec=time.time() - start,
    )
