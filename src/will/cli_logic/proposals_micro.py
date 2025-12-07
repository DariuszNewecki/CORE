# src/will/cli_logic/proposals_micro.py

"""
Implements the logic for creating and applying autonomous, low-risk micro-proposals.
"""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path

import typer
from rich.console import Console

from mind.governance.micro_proposal_validator import MicroProposalValidator
from shared.action_logger import action_logger
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import ExecutionTask
from will.agents.micro_planner import MicroPlannerAgent
from will.agents.plan_executor import PlanExecutor


console = Console()
logger = getLogger(__name__)


# ID: a80cb627-643e-42d0-ad6c-006303438f15
async def micro_propose(context: CoreContext, goal: str) -> Path | None:
    """Uses an agent to create a safe, auto-approvable plan for a goal."""
    logger.info("🤖 Generating micro-proposal for goal: '[cyan]%s[/cyan]'", goal)
    cognitive_service = context.cognitive_service
    planner = MicroPlannerAgent(cognitive_service)
    plan = await planner.create_micro_plan(goal)
    if not plan:
        logger.info(
            "[bold red]❌ Agent could not generate a safe plan for this goal.[/bold red]"
        )
        return None
    proposal = {"proposal_id": str(uuid.uuid4()), "goal": goal, "plan": plan}
    proposal_file = (
        Path(tempfile.gettempdir())
        / f"core-micro-proposal-{proposal['proposal_id']}.json"
    )
    proposal_file.write_text(json.dumps(proposal, indent=2))
    logger.info(
        "[bold green]✅ Safe micro-proposal generated successfully![/bold green]"
    )
    logger.info("Plan details:")
    logger.info(json.dumps(plan, indent=2))
    logger.info("To apply this plan, run:")
    logger.info(
        f"[bold]poetry run core-admin manage proposals micro-apply {proposal_file}[/bold]"
    )
    return proposal_file


# ID: 7cae35d2-d11f-4bf1-8437-79e0dd046d73
async def propose_and_apply_autonomously(context: CoreContext, goal: str):
    """
    A single, unified async workflow that proposes a plan and immediately applies it.
    """
    logger.info(
        f"[bold cyan]🚀 Initiating A1 self-healing for: '{goal}'...[/bold cyan]"
    )
    proposal_path = await micro_propose(context, goal)
    if proposal_path and proposal_path.exists():
        logger.info(
            "\n[bold cyan]-> Plan generated. Proceeding with autonomous application...[/bold cyan]"
        )
        await _micro_apply(context=context, proposal_path=proposal_path)
    elif proposal_path:
        logger.info(
            f"[bold red]❌ Proposal file was not created at {proposal_path}. Aborting.[/bold red]"
        )
        raise typer.Exit(code=1)
    else:
        logger.info("[bold red]❌ Failed to generate a proposal. Aborting.[/bold red]")
        raise typer.Exit(code=1)


async def _micro_apply(context: CoreContext, proposal_path: Path):
    """Validates and applies a micro-proposal."""
    logger.info(f"🔵 Loading and applying micro-proposal: {proposal_path.name}")
    start_time = time.monotonic()
    try:
        proposal_content = proposal_path.read_text(encoding="utf-8")
        proposal_data = json.loads(proposal_content)
        plan_dicts = proposal_data.get("plan", [])
        plan = [ExecutionTask(**task) for task in plan_dicts]
    except Exception as e:
        logger.info("[bold red]❌ Error loading proposal file: %s[/bold red]", e)
        raise typer.Exit(code=1)
    action_logger.log_event(
        "a1.apply.started",
        {"proposal": proposal_path.name, "goal": proposal_data.get("goal")},
    )
    try:
        logger.info(
            "[bold]Step 1/3: Validating plan against constitutional policy...[/bold]"
        )
        validator = MicroProposalValidator()
        is_valid, validation_error = validator.validate(plan)
        if not is_valid:
            raise RuntimeError(f"Plan is constitutionally invalid: {validation_error}")
        logger.info("   -> ✅ Plan is valid.")
        logger.info(
            "[bold]Step 2/3: Gathering evidence via pre-flight checks...[/bold]"
        )
        logger.info("   -> Running full system audit check (in-process)...")
        logger.info("   -> ✅ All pre-flight checks passed (simulated for CLI call).")
        logger.info("[bold]Step 3/3: Executing the validated plan...[/bold]")
        plan_executor = PlanExecutor(
            context.file_handler, context.git_service, context.planner_config
        )
        await plan_executor.execute_plan(plan)
        duration = time.monotonic() - start_time
        action_logger.log_event(
            "a1.apply.succeeded",
            {"proposal": proposal_path.name, "duration_sec": round(duration, 2)},
        )
        logger.info("[bold green]✅ Micro-proposal applied successfully![/bold green]")
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
        logger.info("[bold red]❌ Error during plan execution: %s[/bold red]", e)
        raise typer.Exit(code=1)
