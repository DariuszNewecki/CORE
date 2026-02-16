# src/body/cli/logic/interactive_test/steps/generation.py
# ID: 7527c3dc-8012-4da6-828b-ff9b3900de41

"""
Interactive Code Generation Step Handler.

HEALED (V2.3.0):
- Method Alignment: Updated call to use 'generate_or_repair' instead of obsolete
  'generate_and_validate_code_for_task'.
- Signature Alignment: Matches CoderAgent V2.6 reflexive API.
"""

from __future__ import annotations

from body.cli.logic.interactive_test.ui import (
    prompt_user,
    show_full_code,
    show_progress,
    show_step_header,
    show_success_indicator,
    wait_for_continue,
)
from shared.logger import getLogger
from shared.models import ExecutionTask, TaskParams

from .utils import open_in_editor_async


logger = getLogger(__name__)


# ID: 6fe601c8-9462-4995-a97c-93b4bec37b77
async def step_generate_code(session, target_file, coder_agent):
    """
    Step 1: Orchestrate initial code generation.
    """
    show_step_header(1, 5, "🔍 GENERATE CODE")
    show_progress("Calling LLM to generate test code...")
    show_progress("Reading target file with architectural context...")

    # Define the task
    task = ExecutionTask(
        step=f"Create comprehensive test file for {target_file}",
        action="file.create",
        params=TaskParams(
            file_path=f"tests/{target_file.replace('src/', '').replace('.py', '')}/test_generated.py"
        ),
    )
    goal = f"Generate comprehensive tests for {target_file}"

    try:
        # HEALED: Use the correct reflexive method name from CoderAgent V2.6+
        generated_code = await coder_agent.generate_or_repair(task=task, goal=goal)

        line_count = len(generated_code.splitlines())
        show_progress(f"Generated {line_count} lines of test code")
        artifact_path = session.save_artifact("step1_generated.py", generated_code)

        while True:
            choice = prompt_user(
                title="STEP 1: CODE GENERATED",
                message=f"  ✅ Generated {line_count} lines of test code",
                options={
                    "c": "Continue to next step",
                    "v": "View full output",
                    "e": "Edit in $EDITOR",
                    "r": "Regenerate (new LLM call)",
                    "q": "Quit",
                },
                preview=generated_code,
                artifact_path=artifact_path,
            )
            session.save_decision("generate", choice, {"lines": line_count})

            if choice == "q":
                return False, ""
            if choice == "v":
                show_full_code(generated_code)
                wait_for_continue()
                continue
            if choice == "e":
                if await open_in_editor_async(artifact_path):
                    generated_code = artifact_path.read_text(encoding="utf-8")
                    show_success_indicator("Edits saved")
                return True, generated_code
            if choice == "r":
                # Recursive call for regeneration
                return await step_generate_code(session, target_file, coder_agent)
            if choice == "c":
                return True, generated_code

    except Exception as e:
        logger.error("Code generation failed: %s", e, exc_info=True)
        return False, ""
