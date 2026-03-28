# src/cli/logic/agent.py

"""
Provides a CLI interface for human operators to directly invoke autonomous agent capabilities like application scaffolding.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from body.project_lifecycle.scaffolding_service import Scaffolder
from shared.ai.prompt_model import PromptModel
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)
agent_app = typer.Typer(help="Directly invoke autonomous agent capabilities.")


def _extract_json_from_response(text: str) -> Any:
    """Helper to extract JSON from LLM responses for scaffolding."""
    import re

    match = re.search(
        "```json\\s*(\\{[\\s\\S]*?\\}|\\[[\\s\\S]*?\\])\\s*```", text, re.DOTALL
    )
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


# ID: d3bdf128-7f90-401d-aab8-3f985fd70fb8
async def scaffold_new_application(
    context: CoreContext, project_name: str, goal: str, initialize_git: bool = False
) -> tuple[bool, str]:
    """Uses an LLM to plan and generate a new, multi-file application."""
    logger.info("? Starting to scaffold new application '%s'...", project_name)
    cognitive_service = context.cognitive_service
    await cognitive_service.initialize()
    model = PromptModel.load("scaffold_new_application_prompt")
    try:
        planner_client = await cognitive_service.aget_client_for_role(
            model.manifest.role
        )
        response_text = await model.invoke(
            context={"goal": goal}, client=planner_client, user_id="scaffolding_agent"
        )
        file_structure = _extract_json_from_response(response_text)
        if not isinstance(file_structure, dict):
            raise ValueError("LLM did not return a valid JSON object of files.")
        logger.info("   -> LLM planned a structure with %s files.", len(file_structure))
        scaffolder = Scaffolder(project_name=project_name)
        scaffolder.scaffold_base_structure()
        for rel_path, content in file_structure.items():
            scaffolder.write_file(rel_path, content)
        logger.info("   -> Adding starter test and CI workflow...")
        test_template_path = scaffolder.starter_kit_path / "test_main.py.template"
        ci_template_path = scaffolder.starter_kit_path / "ci.yml.template"
        if test_template_path.exists():
            test_content = test_template_path.read_text(encoding="utf-8").format(
                project_name=project_name
            )
            scaffolder.write_file("tests/test_main.py", test_content)
        if ci_template_path.exists():
            ci_content = ci_template_path.read_text(encoding="utf-8")
            scaffolder.write_file(".github/workflows/ci.yml", ci_content)
        if initialize_git:
            git_service = context.git_service
            logger.info(
                "   -> Initializing new Git repository in %s...",
                scaffolder.project_root,
            )
            git_service.init(scaffolder.project_root)
            scoped_git_service = context.git_service.__class__(scaffolder.project_root)
            scoped_git_service.add_all()
            scoped_git_service.commit(
                f"feat(scaffold): Initial commit for '{project_name}'"
            )
        return (True, f"? Successfully scaffolded '{project_name}'.")
    except Exception as e:
        logger.error("? Scaffolding failed: %s", e, exc_info=True)
        return (False, f"Scaffolding failed: {e!s}")


@agent_app.command("scaffold")
# ID: 92a60ec4-ea5d-41b9-a36d-9687f3faaeda
async def agent_scaffold(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="The directory name for the new application."),
    goal: str = typer.Argument(..., help="A high-level goal for the application."),
    git_init: bool = typer.Option(
        True, "--git/--no-git", help="Initialize a Git repository."
    ),
):
    """Uses an LLM agent to autonomously scaffold a new application."""
    logger.info("? Invoking Agent to scaffold application '%s'...", name)
    logger.info("   -> Goal: '%s'", goal)
    core_context: CoreContext = ctx.obj
    success, message = await scaffold_new_application(
        context=core_context, project_name=name, goal=goal, initialize_git=git_init
    )
    if success:
        typer.secho(f"\n{message}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n{message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
