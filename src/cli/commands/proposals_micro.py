# src/cli/commands/proposals_micro.py
from __future__ import annotations

import asyncio
import json
import tempfile
import uuid
from pathlib import Path

import typer
from rich.console import Console

from core.agents.execution_agent import ExecutionAgent
from core.agents.micro_planner import MicroPlannerAgent
from core.agents.plan_executor import PlanExecutor
from core.prompt_pipeline import PromptPipeline
from core.service_registry import service_registry
from features.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger

console = Console()
log = getLogger("proposals_micro")

micro_app = typer.Typer(help="Manage low-risk, autonomous micro-proposals.")


# ID: 4f17d3f6-36ab-4683-ad2a-dfd9b8221d80
def micro_propose(
    goal: str = typer.Argument(..., help="The high-level goal to achieve.")
):
    """Uses an agent to create a safe, auto-approvable plan for a goal."""
    console.print(f"🤖 Generating micro-proposal for goal: '[cyan]{goal}[/cyan]'")

    cognitive_service = service_registry.get_service("cognitive_service")
    planner = MicroPlannerAgent(cognitive_service)

    plan = asyncio.run(planner.create_micro_plan(goal))

    if not plan:
        console.print(
            "[bold red]❌ Agent could not generate a safe plan for this goal.[/bold red]"
        )
        raise typer.Exit(code=1)

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
        f"[bold]poetry run core-admin proposals micro apply {proposal_file}[/bold]"
    )


@micro_app.command("apply")
# ID: 96a9659e-613a-4403-8cbe-623fa793a19f
def micro_apply(
    proposal_path: Path = typer.Argument(
        ..., help="Path to the micro-proposal JSON file.", exists=True
    )
):
    """Validates and applies a micro-proposal."""
    console.print(f"🔵 Loading and applying micro-proposal: {proposal_path.name}")

    try:
        proposal_content = proposal_path.read_text(encoding="utf-8")
        proposal_data = json.loads(proposal_content)
    except Exception as e:
        console.print(f"[bold red]❌ Error loading proposal file: {e}[/bold red]")
        raise typer.Exit(code=1)

    original_plan = proposal_data.get("plan", [])
    if not original_plan:
        console.print("[bold red]❌ Proposal file contains an empty plan.[/bold red]")
        raise typer.Exit(code=1)

    console.print("Original plan from MicroPlannerAgent:")
    console.print(json.dumps(original_plan, indent=2))

    execution_plan = original_plan

    for step in execution_plan:
        if not isinstance(step, dict) or "action" not in step or "params" not in step:
            console.print(f"[bold red]❌ Invalid plan step format: {step}[/bold red]")
            raise typer.Exit(code=1)

    console.print("Translated/Validated plan for ExecutionAgent:")
    console.print(json.dumps(execution_plan, indent=2))

    try:
        cognitive_service = service_registry.get_service("cognitive_service")
        prompt_pipeline = PromptPipeline(settings.REPO_PATH)
        plan_executor = PlanExecutor()
        auditor_context = AuditorContext(repo_path=settings.REPO_PATH)

        execution_agent = ExecutionAgent(
            cognitive_service=cognitive_service,
            prompt_pipeline=prompt_pipeline,
            plan_executor=plan_executor,
            auditor_context=auditor_context,
        )

        success = asyncio.run(
            execution_agent.execute_plan(
                high_level_goal=proposal_data.get("goal", ""), plan=execution_plan
            )
        )

        if success:
            console.print(
                "[bold green]✅ Micro-proposal applied successfully![/bold green]"
            )
        else:
            console.print(
                "[bold red]❌ ExecutionAgent reported failure during plan application.[/bold red]"
            )
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]❌ Error during plan execution: {e}[/bold red]")
        raise typer.Exit(code=1)


micro_app.command("propose")(micro_propose)

if __name__ == "__main__":
    micro_app()
