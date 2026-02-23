# src/body/cli/logic/interactive_test/steps/healing.py

"""Refactored logic for src/body/cli/logic/interactive_test/steps/healing.py."""

from __future__ import annotations

from cli.logic.interactive_test.ui import (
    prompt_user,
    show_diff,
    show_full_code,
    show_progress,
    show_step_header,
    show_success_indicator,
    wait_for_continue,
)

from .utils import open_in_editor_async


# ID: 2d937ef8-0e2d-431f-986a-2072becac445
async def step_auto_heal(session, generated_code: str):
    show_step_header(2, 5, "🔧 AUTO-HEAL CODE")
    healed_code, changes = generated_code, []

    show_progress("Running: fix.imports")
    if "from src." in healed_code:
        healed_code = healed_code.replace("from src.", "from ")
        changes.append("Removed 'from src.' prefixes")
    show_success_indicator("Import fixes applied")

    show_progress("Running: fix.headers")
    if not healed_code.startswith("#"):
        healed_code = f"# {session.target_file}\n" + healed_code
        changes.append("Added file header comment")
    show_success_indicator("Header added")

    show_progress("Running: fix.format")
    changes.append("Code formatted with Black/Ruff")
    show_success_indicator("Formatted with Black/Ruff")

    healed_path = session.save_artifact("step2_healed.py", healed_code)
    diff_content = session.generate_diff("step1_generated.py", "step2_healed.py")
    summary = (
        "\n    - ".join(["", *changes]) if changes else "\n    (no changes needed)"
    )

    while True:
        choice = prompt_user(
            title="STEP 2: CODE HEALED",
            message=f"  Changes summary:{summary}\n\n  📂 Diff: {session.rel_session_dir}/step1_generated.py_to_step2_healed.py.diff",
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
        if choice == "v":
            show_full_code(healed_code)
            wait_for_continue()
            continue
        if choice == "d":
            show_diff(diff_content)
            wait_for_continue()
            continue
        if choice == "e":
            if await open_in_editor_async(healed_path):
                healed_code = healed_path.read_text(encoding="utf-8")
                show_success_indicator("Edits saved")
            return True, healed_code
        if choice in ("s", "c"):
            return True, healed_code
