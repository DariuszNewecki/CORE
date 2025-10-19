# src/features/self_healing/full_project_remediation.py
"""
Complex, strategic test generation for entire project.

Follows the constitutional remediation process:
1. Strategic Analysis - Identify gaps and prioritize modules
2. Goal Generation - Create executable test generation tasks
3. Test Generation - Autonomously write and validate tests in batches
4. Integration - Report results and track metrics
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cognitive_service import CognitiveService
from rich.console import Console
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext
from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.test_generator import TestGenerator

log = getLogger(__name__)
console = Console()


@dataclass
# ID: a3ac585f-498d-4b69-8bc1-0f4fa697ba5a
class TestGoal:
    """Represents a single test generation goal."""

    module: str
    test_file: str
    priority: int
    current_coverage: float
    target_coverage: float
    goal: str


# ID: 4d73dfe3-fe01-47fc-82ed-444d2849daab
class FullProjectRemediationService:
    """
    Orchestrates autonomous test generation for the entire project.

    This is the complex path with strategic planning, prioritization,
    and batch processing.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
    ):
        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.analyzer = CoverageAnalyzer()
        self.generator = TestGenerator(cognitive_service, auditor_context)

        # Load configuration from policy
        policy = settings.load("charter.policies.governance.quality_assurance_policy")
        self.config = policy.get("coverage_config", {}).get("remediation_config", {})

        self.work_dir = Path(self.config.get("work_directory", "work/testing"))
        self.strategy_dir = self.work_dir / "strategy"
        self.goals_dir = self.work_dir / "goals"
        self.logs_dir = self.work_dir / "logs"

        # Create work directories
        for dir_path in [self.strategy_dir, self.goals_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    # ID: 83ccb4eb-2cd3-4ae1-ad06-6133ccfdd8a8
    async def remediate(self) -> dict[str, Any]:
        """
        Main entry point for full-project coverage remediation.

        Returns:
            Dict with remediation results and metrics
        """
        console.print(
            "\n[bold cyan]🤖 Constitutional Coverage Remediation Activated[/bold cyan]"
        )
        console.print(
            f"   Target: {self.config.get('minimum_threshold', 75)}% coverage\n"
        )

        # Phase 1: Strategic Analysis
        strategy = await self._analyze_gaps()
        if not strategy:
            console.print("[yellow]⚠️  Could not generate testing strategy[/yellow]")
            return {"status": "failed", "phase": "analysis"}

        # Phase 2: Goal Generation
        goals = await self._generate_goals(strategy)
        if not goals:
            console.print("[yellow]⚠️  Could not generate test goals[/yellow]")
            return {"status": "failed", "phase": "goal_generation"}

        console.print(f"[green]✅ Generated {len(goals)} test goals[/green]\n")

        # Phase 3: Test Generation
        results = await self._generate_tests(goals)

        # Phase 4: Report results
        return self._summarize_results(results)

    async def _analyze_gaps(self) -> dict[str, Any] | None:
        """
        Phase 1: Analyze codebase and identify testing priorities.
        """
        console.print("[bold]📊 Phase 1: Strategic Analysis[/bold]")

        # Get current coverage by module
        coverage_data = self.analyzer.get_module_coverage()

        # Analyze codebase structure
        module_info = self.analyzer.analyze_codebase()

        # Build strategy generation prompt
        prompt = self._build_strategy_prompt(coverage_data, module_info)

        # Get AI client and generate strategy
        client = await self.cognitive.aget_client_for_role("Planner")
        response = await client.make_request_async(
            prompt,
            user_id="coverage_remediation",
        )

        # Save strategy
        strategy_file = self.strategy_dir / "test_plan.md"
        strategy_file.write_text(response)

        console.print(f"[green]✅ Strategy saved to {strategy_file}[/green]")

        return {
            "strategy_file": str(strategy_file),
            "coverage_data": coverage_data,
            "module_info": module_info,
        }

    async def _generate_goals(self, strategy: dict) -> list[TestGoal]:
        """
        Phase 2: Convert strategy into executable test generation goals.
        """
        console.print("\n[bold]📋 Phase 2: Goal Generation[/bold]")

        strategy_file = Path(strategy["strategy_file"])
        strategy_text = strategy_file.read_text()

        # Build goal generation prompt
        prompt = f"""Based on this testing strategy, generate a JSON array of test goals.

Each goal should have:
- module: The Python module path (e.g., "core.prompt_pipeline")
- test_file: Corresponding test file path (e.g., "tests/core/test_prompt_pipeline.py")
- priority: Integer 1-10 (1=highest)
- current_coverage: Current coverage percentage
- target_coverage: Target coverage percentage
- goal: A concise description of what tests to create

Strategy:
{strategy_text}

Return ONLY valid JSON starting with [ and ending with ].
"""

        client = await self.cognitive.aget_client_for_role("Planner")
        response = await client.make_request_async(
            prompt,
            user_id="coverage_remediation",
        )

        # Parse goals from response
        try:
            # Extract JSON from response
            json_start = response.find("[")
            json_end = response.rfind("]") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                goals_data = json.loads(json_str)

                goals = [TestGoal(**g) for g in goals_data]

                # Save goals
                goals_file = self.goals_dir / "test_goals.json"
                goals_file.write_text(json.dumps(goals_data, indent=2))

                console.print(f"[green]✅ Goals saved to {goals_file}[/green]")

                return goals
        except Exception as e:
            log.error(f"Failed to parse goals: {e}")
            console.print(f"[red]❌ Failed to parse goals: {e}[/red]")

        return []

    async def _generate_tests(self, goals: list[TestGoal]) -> dict[str, Any]:
        """
        Phase 3: Generate tests for each goal in batches.
        """
        console.print("\n[bold]🧪 Phase 3: Test Generation[/bold]\n")

        batch_size = self.config.get("batch_size", 5)
        max_iterations = self.config.get("max_iterations", 10)

        succeeded = 0
        failed = 0
        results = []

        for i in range(0, len(goals), batch_size):
            if i // batch_size >= max_iterations:
                console.print(
                    f"[yellow]⚠️  Reached max iterations ({max_iterations})[/yellow]"
                )
                break

            batch = goals[i : i + batch_size]
            console.print(
                f"[cyan]Processing batch {i // batch_size + 1} ({len(batch)} goals)[/cyan]"
            )

            for goal in batch:
                try:
                    # --- THIS IS THE FIX ---
                    # Use the correct keyword arguments for the generate_test method.
                    result = await self.generator.generate_test(
                        module_path=goal.module,
                        test_file=goal.test_file,
                        goal=goal.goal,
                        target_coverage=goal.target_coverage,
                    )
                    # --- END OF FIX ---

                    if result.get("status") == "success":
                        succeeded += 1
                        console.print(f"  [green]✅ {goal.module}[/green]")
                    else:
                        failed += 1
                        console.print(
                            f"  [red]❌ {goal.module}: {result.get('error', 'Unknown error')}[/red]"
                        )

                    results.append({"goal": goal, "result": result})

                except Exception as e:
                    failed += 1
                    log.error(f"Test generation failed for {goal.module}: {e}")
                    console.print(f"  [red]❌ {goal.module}: {e}[/red]")

            # Cooldown between batches
            if i + batch_size < len(goals):
                cooldown = self.config.get("cooldown_seconds", 10)
                console.print(f"[dim]Cooling down for {cooldown}s...[/dim]\n")
                await asyncio.sleep(cooldown)

        return {
            "succeeded": succeeded,
            "failed": failed,
            "total": len(goals),
            "results": results,
        }

    def _summarize_results(self, results: dict) -> dict[str, Any]:
        """
        Phase 4: Summarize and report results.
        """
        console.print("\n[bold]📈 Remediation Summary[/bold]\n")

        succeeded = results["succeeded"]
        failed = results["failed"]
        total = results["total"]

        console.print(f"Total Goals: {total}")
        console.print(f"[green]✅ Succeeded: {succeeded}[/green]")
        console.print(f"[red]❌ Failed: {failed}[/red]")

        # Measure final coverage
        final_coverage = self._measure_final_coverage()

        return {
            "status": "completed" if succeeded > 0 else "failed",
            "succeeded": succeeded,
            "failed": failed,
            "total": total,
            "final_coverage": final_coverage,
        }

    def _build_strategy_prompt(self, coverage_data: dict, module_info: dict) -> str:
        """Build the strategy generation prompt."""
        # Load strategy prompt template
        strategy_prompt_file = (
            settings.REPO_PATH / ".intent/mind/prompts/coverage_strategy.prompt"
        )
        if strategy_prompt_file.exists():
            template = strategy_prompt_file.read_text()
        else:
            template = "Analyze coverage and create a testing strategy."

        # Format with data
        prompt = f"""{template}

## Coverage Data
{json.dumps(coverage_data, indent=2)}

## Module Information
{json.dumps(module_info, indent=2)}

Generate a comprehensive testing strategy in Markdown format.
"""
        return prompt

    def _measure_final_coverage(self) -> float:
        """Measure final coverage percentage."""
        coverage_data = self.analyzer.measure_coverage()
        if coverage_data:
            percent = coverage_data.get("overall_percent", 0)
            console.print(f"\n[bold]Final Coverage: {percent}%[/bold]")
            return percent
        return 0.0
