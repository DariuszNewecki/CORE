# src/cli/logic/proposals_micro.py
from __future__ import annotations

import asyncio
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import typer
from core.agents.execution_agent import ExecutionAgent
from core.agents.micro_planner import MicroPlannerAgent
from core.agents.plan_executor import PlanExecutor
from core.prompt_pipeline import PromptPipeline
from features.governance.constitutional_auditor import ConstitutionalAuditor
from features.governance.micro_proposal_validator import MicroProposalValidator
from rich.console import Console
from shared.action_logger import action_logger
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import ExecutionTask, PlannerConfig

console = Console()
log = getLogger("proposals_micro")

micro_app = typer.Typer(help="Manage low-risk, autonomous micro-proposals.")


# --- MODIFICATION: This function is now async and renamed for clarity ---
async def _create_micro_proposal(
    context: CoreContext,
    goal: str,
) -> Optional[Path]:
    """Uses an agent to create a safe, auto-approvable plan for a goal."""
    console.print(f"🤖 Generating micro-proposal for goal: '[cyan]{goal}[/cyan]'")

    cognitive_service = context.cognitive_service
    planner = MicroPlannerAgent(cognitive_service)

    # Use await instead of asyncio.run()
    plan = await planner.create_micro_plan(goal)

    if not plan:
        console.print(
            "[bold red]❌ Agent could not generate a safe plan for this goal.[/bold red]"
        )
        return None

    proposal = {"proposal_id": str(uuid.uuid4()), "goal": goal, "plan": plan}
    proposal_file = (
        Path(tempfile.gettempdir())
        / f"core-micro-proposal-{proposal['proposal_id']}.json"
    )
    proposal_file.write_text(json.dumps(proposal, indent=2))

    console.print(
        "[bold green]✅ Safe micro-proposal generated successfully![/bold green]"
    )
    console.print("Plan details:")
    console.print(json.dumps(plan, indent=2))
    console.print("To apply this plan, run:")
    console.print(
        f"[bold]poetry run core-admin manage proposals micro apply {proposal_file}[/bold]"
    )
    return proposal_file


# --- NEW ORCHESTRATOR FUNCTION ---
# ID: 1494aa0f-9e85-4675-8bc4-7c69529206c4
async def propose_and_apply_autonomously(context: CoreContext, goal: str):
    """
    A single, unified async workflow that proposes a plan and immediately applies it.
    This runs in a single event loop, avoiding concurrency errors.
    """
    console.print(
        f"[bold cyan]🚀 Initiating A1 self-healing for: '{goal}'...[/bold cyan]"
    )
    proposal_path = await _create_micro_proposal(context, goal)

    if proposal_path and proposal_path.exists():
        console.print(
            "\n[bold cyan]-> Plan generated. Proceeding with autonomous application...[/bold cyan]"
        )
        await micro_apply(context=context, proposal_path=proposal_path)
    elif proposal_path:
        console.print(
            f"[bold red]❌ Proposal file was not created at {proposal_path}. Aborting.[/bold red]"
        )
        raise typer.Exit(code=1)
    else:
        console.print(
            "[bold red]❌ Failed to generate a proposal. Aborting.[/bold red]"
        )
        raise typer.Exit(code=1)


# ID: 580abe43-41ff-4f50-b734-177b2a547cc9
async def micro_apply(
    context: CoreContext,
    proposal_path: Path,
):
    """Validates and applies a micro-proposal."""
    console.print(f"🔵 Loading and applying micro-proposal: {proposal_path.name}")
    start_time = time.monotonic()

    try:
        proposal_content = proposal_path.read_text(encoding="utf-8")
        proposal_data = json.loads(proposal_content)
        plan_dicts = proposal_data.get("plan", [])
        plan = [ExecutionTask(**task) for task in plan_dicts]
    except Exception as e:
        console.print(f"[bold red]❌ Error loading proposal file: {e}[/bold red]")
        raise typer.Exit(code=1)

    action_logger.log_event(
        "a1.apply.started",
        {"proposal": proposal_path.name, "goal": proposal_data.get("goal")},
    )

    try:
        # 1. Zero-Trust Validation
        console.print(
            "[bold]Step 1/3: Validating plan against constitutional policy...[/bold]"
        )
        validator = MicroProposalValidator()
        is_valid, validation_error = validator.validate(plan)
        if not is_valid:
            raise RuntimeError(f"Plan is constitutionally invalid: {validation_error}")
        console.print("   -> ✅ Plan is valid.")

        # 2. Gather Evidence via CI Checks (IN-PROCESS)
        console.print(
            "[bold]Step 2/3: Gathering evidence via pre-flight checks...[/bold]"
        )
        console.print("   -> Running full system audit check (in-process)...")

        auditor = ConstitutionalAuditor(context.auditor_context)
        passed, findings, _ = await auditor.run_full_audit_async()

        if not passed:
            error_details = "\n".join(
                [f.message for f in findings if f.severity.is_blocking]
            )
            raise RuntimeError(f"Pre-flight audit check failed:\n{error_details}")

        console.print("   -> ✅ All pre-flight checks passed.")

        # 3. Apply the Change via ExecutionAgent
        console.print("[bold]Step 3/3: Executing the validated plan...[/bold]")
        prompt_pipeline = PromptPipeline(settings.REPO_PATH)
        plan_executor = PlanExecutor(
            file_handler=context.file_handler,
            git_service=context.git_service,
            config=PlannerConfig(),
        )
        auditor_context = context.auditor_context
        coder_agent = __import__(
            "core.agents.coder_agent"
        ).agents.coder_agent.CoderAgent(
            cognitive_service=context.cognitive_service,
            prompt_pipeline=prompt_pipeline,
            auditor_context=auditor_context,
        )
        execution_agent = ExecutionAgent(
            coder_agent=coder_agent,
            plan_executor=plan_executor,
            auditor_context=auditor_context,
        )
        success, message = await execution_agent.execute_plan(
            high_level_goal=proposal_data.get("goal", ""), plan=plan
        )
        if not success:
            raise RuntimeError(
                f"ExecutionAgent reported failure during plan application: {message}"
            )

        duration = time.monotonic() - start_time
        action_logger.log_event(
            "a1.apply.succeeded",
            {"proposal": proposal_path.name, "duration_sec": round(duration, 2)},
        )
        console.print(
            "[bold green]✅ Micro-proposal applied successfully![/bold green]"
        )

    except Exception as e:
        duration = time.monotonic() - start_time
        action_logger.log_event(
            "a1.apply.failed",
            {
                "proposal": proposal_path.name,
                "error": str(e),
                "duration_sec": round(duration, 2),
            },
        )
        console.print(f"[bold red]❌ Error during plan execution: {e}[/bold red]")
        raise typer.Exit(code=1)


# ID: 6af5f17c-1975-447c-9c2c-c90e2095ce34
def register(app: typer.Typer, context: CoreContext):
    """Register the 'micro' command group with a parent Typer app."""

    @micro_app.command("apply")
    # ID: f84ebe0a-f814-4cb3-a54b-5c186d4733c9
    def apply_command_wrapper(
        ctx: typer.Context,
        proposal_path: Path = typer.Argument(
            ..., help="Path to the micro-proposal JSON file.", exists=True
        ),
    ):
        """Wrapper to pass CoreContext to the micro_apply logic."""
        core_context: CoreContext = ctx.obj
        asyncio.run(micro_apply(context=core_context, proposal_path=proposal_path))

    @micro_app.command("propose")
    # ID: 5336b8a6-6f19-46a1-b8d2-9d3d83e8e3d3
    def propose_command_wrapper(
        ctx: typer.Context,
        goal: str = typer.Argument(..., help="The high-level goal to achieve."),
    ):
        """Wrapper to pass CoreContext to the micro_propose logic."""
        core_context: CoreContext = ctx.obj
        # This remains synchronous for dry-run purposes
        asyncio.run(_create_micro_proposal(context=core_context, goal=goal))

    app.add_typer(micro_app, name="micro")
