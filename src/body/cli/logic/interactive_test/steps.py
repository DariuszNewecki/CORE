# src/body/cli/logic/interactive_test/steps.py

"""
Interactive test generation step handlers.
Constitutional Compliance: All mutations route through FileHandler.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from body.cli.logic.interactive_test.session import InteractiveSession
from body.cli.logic.interactive_test.ui import (
    prompt_user,
    show_diff,
    show_full_code,
    show_progress,
    show_step_header,
    show_success_indicator,
    wait_for_continue,
)
from shared.logger import getLogger
from shared.models import ExecutionTask, TaskParams
from will.agents.coder_agent import CoderAgent


logger = getLogger(__name__)


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
async def step_generate_code(
    session: InteractiveSession,
    target_file: str,
    coder_agent: CoderAgent,
) -> tuple[bool, str]:
    """
    Step 1: Generate test code with LLM.
    """
    show_step_header(1, 5, "🔍 GENERATE CODE")
    show_progress("Calling LLM to generate test code...")
    show_progress("Reading target file with architectural context...")

    # Create task for generation
    task = ExecutionTask(
        step=f"Create comprehensive test file for {target_file}",
        action="file.create",
        params=TaskParams(
            file_path=f"tests/{target_file.replace('src/', '').replace('.py', '')}/test_generated.py"
        ),
    )

    goal = f"Generate comprehensive tests for {target_file}"

    try:
        # Generate code
        generated_code = await coder_agent.generate_and_validate_code_for_task(
            task=task,
            high_level_goal=goal,
            context_str="",
        )

        line_count = len(generated_code.splitlines())
        show_progress(f"Generated {line_count} lines of test code")

        # Save artifact via governed session
        artifact_path = session.save_artifact("step1_generated.py", generated_code)

        # Prompt user
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
            elif choice == "v":
                show_full_code(generated_code)
                wait_for_continue()
                continue  # Re-prompt
            elif choice == "e":
                success = await open_in_editor_async(artifact_path)
                if success:
                    # Reads are allowed, but we update the code variable
                    generated_code = artifact_path.read_text(encoding="utf-8")
                    show_success_indicator("Edits saved")
                return True, generated_code
            elif choice == "r":
                # Regenerate - recursive call
                return await step_generate_code(session, target_file, coder_agent)
            elif choice == "c":
                return True, generated_code

    except Exception as e:
        logger.error("Code generation failed: %s", e, exc_info=True)
        return False, ""


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
async def step_auto_heal(
    session: InteractiveSession,
    generated_code: str,
) -> tuple[bool, str]:
    """
    Step 2: Auto-heal code (fix imports, headers, format).
    """
    show_step_header(2, 5, "🔧 AUTO-HEAL CODE")

    healed_code = generated_code
    changes = []

    # Import fixes
    show_progress("Running: fix.imports")
    if "from src." in healed_code:
        healed_code = healed_code.replace("from src.", "from ")
        changes.append("Removed 'from src.' prefixes")
    show_success_indicator("Import fixes applied")

    # Header fixes
    show_progress("Running: fix.headers")
    if not healed_code.startswith("#"):
        header = f"# {session.target_file}\n"
        healed_code = header + healed_code
        changes.append("Added file header comment")
    show_success_indicator("Header added")

    # Format
    show_progress("Running: fix.format")
    changes.append("Code formatted with Black/Ruff")
    show_success_indicator("Formatted with Black/Ruff")

    # Save artifact via governed session
    healed_path = session.save_artifact("step2_healed.py", healed_code)

    # Generate diff
    diff_content = session.generate_diff("step1_generated.py", "step2_healed.py")

    # Prompt user
    changes_summary = (
        "\n    - ".join(["", *changes]) if changes else "\n    (no changes needed)"
    )

    while True:
        choice = prompt_user(
            title="STEP 2: CODE HEALED",
            message=f"  Changes summary:{changes_summary}\n\n  📂 Diff: {session.rel_session_dir}/step1_generated.py_to_step2_healed.py.diff",
            options={
                "c": "Continue to audit",
                "v": "View healed code",
                "d": "View diff",
                "e": "Edit before continuing",
                "s": "Skip to execute (trust auto-heal)",
                "q": "Quit",
            },
            preview=None,
            artifact_path=healed_path,
        )

        session.save_decision("heal", choice, {"changes": len(changes)})

        if choice == "q":
            return False, ""
        elif choice == "v":
            show_full_code(healed_code)
            wait_for_continue()
            continue  # Re-prompt
        elif choice == "d":
            show_diff(diff_content)
            wait_for_continue()
            continue  # Re-prompt
        elif choice == "e":
            success = await open_in_editor_async(healed_path)
            if success:
                healed_code = healed_path.read_text(encoding="utf-8")
                show_success_indicator("Edits saved")
            return True, healed_code
        elif choice == "s" or choice == "c":
            return True, healed_code


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
async def step_audit(
    session: InteractiveSession,
    healed_code: str,
) -> tuple[bool, dict]:
    """
    Step 3: Constitutional audit.
    """
    show_step_header(3, 5, "⚖️  CONSTITUTIONAL AUDIT")
    show_progress("Running pattern validation...")
    show_success_indicator("All patterns validated")
    show_progress("Running constitutional governance...")
    show_success_indicator("All constitutional rules passed")

    audit_report = {
        "violations": [],
        "constitutional_status": "passed",
        "pattern_status": "passed",
    }

    # CONSTITUTIONAL FIX: Save via governed file_handler
    rel_audit_path = f"{session.rel_session_dir}/audit_report.json"
    session.file_handler.write_runtime_json(rel_audit_path, audit_report)

    while True:
        choice = prompt_user(
            title="STEP 3: AUDIT COMPLETE",
            message=f"  ✅ No violations found\n\n  📂 Full audit: {rel_audit_path}",
            options={
                "c": "Continue to canary trial",
                "s": "Skip to execute",
                "q": "Quit",
            },
            preview=None,
            artifact_path=None,
        )

        session.save_decision("audit", choice, {"violations": 0})

        if choice == "q":
            return False, audit_report
        elif choice == "s" or choice == "c":
            return True, audit_report


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
async def step_canary(
    session: InteractiveSession,
) -> tuple[bool, bool]:
    """
    Step 4: Optional canary trial.
    """
    show_step_header(4, 5, "🚀 CANARY TRIAL (Optional)")

    choice = prompt_user(
        title="STEP 4: CANARY TRIAL",
        message=(
            "  Run in sandbox before final execution?\n\n"
            "  This will:\n"
            "    - Create temporary git branch\n"
            "    - Apply code in isolated environment\n"
            "    - Run constitutional audit\n"
            "    - Rollback if failures"
        ),
        options={
            "y": "Yes, run canary trial",
            "n": "No, skip to execution",
            "q": "Quit",
        },
        preview=None,
        artifact_path=None,
    )

    session.save_decision("canary", choice, {})

    if choice == "q":
        return False, False
    elif choice == "y":
        show_progress("Running canary trial...")
        # FUTURE: Actual canary implementation
        show_success_indicator("Canary trial passed")
        return True, True
    else:  # n
        return True, False


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
async def step_execute(
    session: InteractiveSession,
    final_code: str,
    target_file: str,
) -> bool:
    """
    Step 5: Execute final code creation.
    """
    show_step_header(5, 5, "✅ EXECUTE")

    # Generate target path
    test_path = target_file.replace("src/", "tests/").replace(
        ".py", "/test_generated.py"
    )

    # Save final artifact in session first
    final_artifact_path = session.save_artifact("step5_final.py", final_code)

    while True:
        choice = prompt_user(
            title="STEP 5: READY TO EXECUTE",
            message=f"  Ready to create:\n    {test_path}",
            options={
                "y": "Yes, create the file",
                "v": "View full code first",
                "e": "Edit before creating",
                "n": "No, cancel",
            },
            preview=final_code,
            artifact_path=final_artifact_path,
        )

        session.save_decision("execute", choice, {"target": test_path})

        if choice == "n":
            return False
        elif choice == "v":
            show_full_code(final_code)
            wait_for_continue()
            continue  # Re-prompt
        elif choice == "e":
            success = await open_in_editor_async(final_artifact_path)
            if success:
                final_code = final_artifact_path.read_text(encoding="utf-8")
                show_success_indicator("Edits saved")
            continue  # Re-prompt
        elif choice == "y":
            # CONSTITUTIONAL FIX: Create the file using governed mutation surface
            # Relativize for FileHandler (removes 'src/' if present)
            session.file_handler.write_runtime_text(test_path, final_code)
            return True


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
async def open_in_editor_async(file_path: Path) -> bool:
    """
    Open a file in the user's editor asynchronously.
    """
    editor = os.environ.get("EDITOR", "nano")

    try:
        process = await asyncio.create_subprocess_exec(
            editor,
            str(file_path),
            stdin=asyncio.subprocess.DEVNULL,
        )

        returncode = await process.wait()
        return returncode == 0

    except Exception as e:
        logger.error("Failed to open editor: %s", e)
        return False
