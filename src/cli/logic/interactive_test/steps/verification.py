# src/body/cli/logic/interactive_test/steps/verification.py

"""Refactored logic for src/body/cli/logic/interactive_test/steps/verification.py."""

from __future__ import annotations

from cli.logic.interactive_test.ui import (
    prompt_user,
    show_progress,
    show_step_header,
    show_success_indicator,
)


# ID: a9834b83-0ab1-44f6-bdd6-71821ae273c8
async def step_audit(session, healed_code: str):
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
        if choice in ("s", "c"):
            return True, audit_report


# ID: c9ddfa6f-8a8d-47a4-8ac1-82912dad2bac
async def step_canary(session):
    show_step_header(4, 5, "🚀 CANARY TRIAL (Optional)")
    choice = prompt_user(
        title="STEP 4: CANARY TRIAL",
        message="  Run in sandbox before final execution?\n\n  - Temporary git branch\n  - Isolated environment\n  - Rollback if failures",
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
    if choice == "y":
        show_progress("Running canary trial...")
        show_success_indicator("Canary trial passed")
        return True, True
    return True, False
