# src/cli/commands/proposals_micro.py
from __future__ import annotations

import asyncio
import json
import subprocess
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
from features.governance.micro_proposal_validator import MicroProposalValidator
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
        plan = proposal_data.get("plan", [])
    except Exception as e:
        console.print(f"[bold red]❌ Error loading proposal file: {e}[/bold red]")
        raise typer.Exit(code=1)

    # 1. Zero-Trust Validation
    console.print(
        "[bold]Step 1/3: Validating plan against constitutional policy...[/bold]"
    )
    validator = MicroProposalValidator()
    is_valid, validation_error = validator.validate(plan)
    if not is_valid:
        console.print(
            f"[bold red]❌ Plan is constitutionally invalid: {validation_error}[/bold red]"
        )
        raise typer.Exit(code=1)
    console.print("   -> ✅ Plan is valid.")

    # 2. Gather Evidence via CI Checks
    console.print("[bold]Step 2/3: Gathering evidence via pre-flight checks...[/bold]")
    checks = [
        ("lint", "check ci lint"),
        ("test", "check ci test"),
        ("audit", "check ci audit"),
    ]
    for name, command in checks:
        console.print(f"   -> Running {name} check...")
        result = subprocess.run(
            ["poetry", "run", "core-admin", *command.split()],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(
                f"[bold red]❌ Pre-flight '{name}' check failed. Aborting.[/bold red]"
            )
            console.print(result.stderr)
            raise typer.Exit(code=1)
    console.print("   -> ✅ All pre-flight checks passed.")

    # 3. Apply the Change via ExecutionAgent
    console.print("[bold]Step 3/3: Executing the validated plan...[/bold]")
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
                high_level_goal=proposal_data.get("goal", ""), plan=plan
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
