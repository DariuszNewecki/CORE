# src/system/admin/agent.py
"""
Intent: Exposes PlannerAgent capabilities directly to the human operator via the CLI.
"""
from __future__ import annotations

import json
import re
import subprocess
import textwrap
from typing import Any

import typer

from core.clients import OrchestratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from shared.logger import getLogger
from shared.path_utils import get_repo_root
from system.tools.scaffolder import Scaffolder

log = getLogger("core_admin.agent")
CORE_ROOT = get_repo_root()

agent_app = typer.Typer(help="Directly invoke autonomous agent capabilities.")


def _extract_json_from_response(text: str) -> Any:
    """
    Robustly extract the first valid JSON value from a model response.

    Strategy (least → most permissive):
      1) Direct parse if the whole text is JSON.
      2) Trim common wrappers (code fences), try parse.
      3) Find the first balanced JSON object/array in the text and parse that.

    Raises JSONDecodeError if no valid JSON is found.
    """
    s = text.strip()

    # 1) Direct parse
    if s.startswith("{") or s.startswith("["):
        return json.loads(s)

    # 2) Strip common code-fence wrappers like ```json ... ``` or ``` ... ```
    fence = re.compile(r"^```(?:json|JSON)?\s*(.*?)\s*```$", re.DOTALL)
    m = fence.match(s)
    if m:
        inner = m.group(1).strip()
        if inner.startswith("{") or inner.startswith("["):
            return json.loads(inner)

    # Also handle inline fenced blocks appearing anywhere; prefer ```json blocks first
    for pattern in (r"```(?:json|JSON)\s*(.*?)\s*```", r"```\s*(.*?)\s*```"):
        for mm in re.finditer(pattern, s, flags=re.DOTALL):
            candidate = mm.group(1).strip()
            if candidate.startswith("{") or candidate.startswith("["):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # try the next candidate
                    pass

    # 3) Balanced-brace/bracket scan to locate the first JSON value
    def _scan_balanced(src: str) -> str | None:
        """Scan a string for a balanced bracket-enclosed expression (supports {}, [], and nested strings with escapes) and return it if found, else None."""
        openers = {"{": "}", "[": "]"}
        i = 0
        n = len(src)
        while i < n:
            ch = src[i]
            if ch in openers:
                stack = [openers[ch]]
                j = i + 1
                in_str = False
                escape = False
                while j < n:
                    c = src[j]
                    if in_str:
                        if escape:
                            escape = False
                        elif c == "\\":
                            escape = True
                        elif c == '"':
                            in_str = False
                    else:
                        if c == '"':
                            in_str = True
                        elif c in openers:
                            stack.append(openers[c])
                        elif stack and c == stack[-1]:
                            stack.pop()
                            if not stack:
                                return src[i : j + 1]
                    j += 1
            i += 1
        return None

    segment = _scan_balanced(s)
    if segment is not None:
        return json.loads(segment)

    # Give a clear, actionable error
    raise json.JSONDecodeError("No valid JSON found in response", s, 0)


# CAPABILITY: scaffold_project
def scaffold_new_application(
    project_name: str,
    goal: str,
    orchestrator: OrchestratorClient,
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
    response_text: str | None = None  # for better error diagnostics

    try:
        response_text = orchestrator.make_request(
            final_prompt, user_id="scaffolding_agent"
        )
        file_structure = _extract_json_from_response(response_text)

        if not isinstance(file_structure, dict):
            raise ValueError("LLM did not return a valid JSON object of files.")

        log.info(f"   -> LLM planned a structure with {len(file_structure)} files.")

        scaffolder = Scaffolder(project_name=project_name)
        scaffolder.scaffold_base_structure()

        # Write the LLM-generated files
        for rel_path, content in file_structure.items():
            scaffolder.write_file(rel_path, content)

        # Add the templated test and CI files
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

        # Optionally initialize a Git repository and make an initial commit.
        if initialize_git:
            log.info("   -> Initializing Git repository...")
            git = GitService(scaffolder.project_root)
            try:
                # Create a repo if not already a git repo
                if not git.is_git_repo():
                    subprocess.run(
                        ["git", "init"], cwd=scaffolder.project_root, check=True
                    )
                git.add(".")
                git.commit(f"feat(scaffold): Initialize '{project_name}'")
                log.info("   -> ✅ Initial commit created.")
            except Exception as e:
                log.warning(f"   -> ⚠️ Git initialization skipped: {e}")

        return (
            True,
            f"✅ Successfully scaffolded '{project_name}' in '{scaffolder.workspace.relative_to(file_handler.repo_path)}'.",
        )

    except Exception as e:
        # Extra diagnostic preview when the LLM returns non-JSON and parsing fails
        if isinstance(e, json.JSONDecodeError) and response_text:
            preview = response_text.strip().replace("\n", " ")
            if len(preview) > 200:
                preview = preview[:200] + "…"
            log.error("LLM response was not valid JSON. Preview: %r", preview)
        else:
            log.error(f"❌ Scaffolding failed: {e}", exc_info=True)

        # Preserve the original operator-facing message to keep tests and UX stable
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
        orchestrator = OrchestratorClient()
        file_handler = FileHandler(str(CORE_ROOT))
        success, message = scaffold_new_application(
            project_name=name,
            goal=goal,
            orchestrator=orchestrator,
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
