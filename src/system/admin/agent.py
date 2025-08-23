# src/system/admin/agent.py
"""
Intent: Exposes PlannerAgent capabilities directly to the human operator via the CLI.
"""
import json
import subprocess
import textwrap

import typer

# --- FIX: Import the new service, not the old client ---
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from system.tools.scaffolder import Scaffolder

log = getLogger("core_admin.agent")
CORE_ROOT = get_repo_root()

agent_app = typer.Typer(help="Directly invoke autonomous agent capabilities.")


def _extract_json_from_response(text: str):
    """Helper to extract JSON from LLM responses for scaffolding."""
    import re

    match = re.search(r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


# CAPABILITY: scaffold_project
def scaffold_new_application(
    project_name: str,
    goal: str,
    cognitive_service: CognitiveService,  # <-- FIX: Takes the service now
    file_handler: FileHandler,
    initialize_git: bool = False,
) -> tuple[bool, str]:
    """Uses an LLM to plan and generate a new, multi-file application."""
    log.info(f"🌱 Starting to scaffold new application '{project_name}'...")
    prompt_template = textwrap.dedent(
        """
        You are a senior software architect. Your task is to design the file structure and content for a new Python application based on a high-level goal.

        **Goal:** "{goal}"

        **Instructions:**
        1.  Think step-by-step about the necessary files for a minimal, working version.
        2.  Your output MUST be a single, valid JSON object with file paths as keys and content as values.
        3.  Include a `pyproject.toml` and a simple `src/main.py`.
        4.  Keep the code simple, clean, and functional.
        """
    ).strip()

    final_prompt = prompt_template.format(goal=goal)
    try:
        # --- FIX: Use the CognitiveService to get the correct client for the job ---
        planner_client = cognitive_service.get_client_for_role("Planner")
        response_text = planner_client.make_request(
            final_prompt, user_id="scaffolding_agent"
        )
        file_structure = _extract_json_from_response(response_text)

        if not isinstance(file_structure, dict):
            raise ValueError("LLM did not return a valid JSON object of files.")

        log.info(f"   -> LLM planned a structure with {len(file_structure)} files.")

        scaffolder = Scaffolder(project_name=project_name)
        scaffolder.scaffold_base_structure()

        for rel_path, content in file_structure.items():
            scaffolder.write_file(rel_path, content)

        log.info("   -> Adding starter test and CI workflow...")
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
            log.info(
                f"   -> Initializing new Git repository in {scaffolder.project_root}..."
            )
            subprocess.run(
                ["git", "init"],
                cwd=scaffolder.project_root,
                check=True,
                capture_output=True,
            )
            new_repo_git = GitService(str(scaffolder.project_root))
            new_repo_git.add(".")
            new_repo_git.commit(f"feat(scaffold): Initial commit for '{project_name}'")

        return (
            True,
            f"✅ Successfully scaffolded '{project_name}' in '{scaffolder.workspace.relative_to(file_handler.repo_path)}'.",
        )

    except Exception as e:
        log.error(f"❌ Scaffolding failed: {e}", exc_info=True)
        return False, f"Scaffolding failed: {str(e)}"


@agent_app.command("scaffold")
def agent_scaffold(
    name: str = typer.Argument(..., help="The directory name for the new application."),
    goal: str = typer.Argument(..., help="A high-level goal for the application."),
    git_init: bool = typer.Option(
        True, "--git/--no-git", help="Initialize a Git repository."
    ),
):
    """Uses an LLM agent to autonomously scaffold a new application."""
    log.info(f"🤖 Invoking Agent to scaffold application '{name}'...")
    log.info(f"   -> Goal: '{goal}'")

    try:
        # --- FIX: Instantiate the service, not the client ---
        cognitive_service = CognitiveService(CORE_ROOT)
        file_handler = FileHandler(str(CORE_ROOT))
        success, message = scaffold_new_application(
            project_name=name,
            goal=goal,
            cognitive_service=cognitive_service,
            file_handler=file_handler,
            initialize_git=git_init,
        )
    except Exception as e:
        log.error(f"❌ Failed to initialize agent tools: {e}", exc_info=True)
        raise typer.Exit(code=1)

    if success:
        typer.secho(f"\n{message}", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n{message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def register(app: typer.Typer):
    """Register the 'agent' command group with the main CLI app."""
    app.add_typer(agent_app, name="agent")
