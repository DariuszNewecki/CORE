# src/body/cli/logic/interactive_test/steps/execution.py

"""Refactored logic for src/body/cli/logic/interactive_test/steps/execution.py."""

from __future__ import annotations

from body.cli.logic.interactive_test.ui import (
    prompt_user,
    show_full_code,
    show_step_header,
    show_success_indicator,
    wait_for_continue,
)

from .utils import open_in_editor_async


# ID: 531bdd5c-03a2-412e-b663-c51451d52df0
async def step_execute(session, final_code: str, target_file: str):
    show_step_header(5, 5, "✅ EXECUTE")
    test_path = target_file.replace("src/", "tests/").replace(
        ".py", "/test_generated.py"
    )
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
        if choice == "v":
            show_full_code(final_code)
            wait_for_continue()
            continue
        if choice == "e":
            if await open_in_editor_async(final_artifact_path):
                final_code = final_artifact_path.read_text(encoding="utf-8")
                show_success_indicator("Edits saved")
            continue
        if choice == "y":
            session.file_handler.write_runtime_text(test_path, final_code)
            return True
