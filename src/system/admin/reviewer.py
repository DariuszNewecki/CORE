# src/system/admin/reviewer.py
"""
Provides commands for AI-powered review of the constitution, documentation, and source code files.
"""

from __future__ import annotations

# src/system/admin/reviewer.py
"""
Intent: Implements commands related to constitutional review and improvement.
This includes exporting the constitution for external analysis and orchestrating
an AI-powered peer review for both the machine-readable constitution and the
human-readable documentation.
"""

from pathlib import Path
from typing import List, Set

import typer
import yaml
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.review")

# --- Configuration for what to ignore during bundling ---
INTENT_IGNORE_PATTERNS = {"proposals", "knowledge_graph.json", ".bak", ".example"}
DOCS_IGNORE_DIRS = {"assets", "archive", "migrations", "examples"}


def _get_bundle_content(files_to_bundle: List[Path], root_dir: Path) -> str:
    """Generic function to bundle the content of a list of files."""
    bundle_parts = []
    for file_path in sorted(list(files_to_bundle)):
        if file_path.exists() and file_path.is_file():
            try:
                content = file_path.read_text(encoding="utf-8")
                rel_path = file_path.resolve().relative_to(root_dir.resolve())
                bundle_parts.append(f"--- START OF FILE ./{rel_path} ---\n")
                bundle_parts.append(content)
                bundle_parts.append(f"\n--- END OF FILE ./{rel_path} ---\n\n")
            except ValueError:
                log.warning(
                    f"Could not determine relative path for {file_path}. Skipping."
                )
    return "".join(bundle_parts)


def _get_constitutional_files() -> List[Path]:
    """Discovers and returns a list of all machine-readable constitutional files."""
    intent_dir = settings.MIND
    meta_path = intent_dir / "meta.yaml"
    if not meta_path.exists():
        return []

    meta_content = yaml.safe_load(meta_path.read_text(encoding="utf-8"))

    def find_paths_in_meta(data):
        paths = []
        if isinstance(data, dict):
            for value in data.values():
                paths.extend(find_paths_in_meta(value))
        elif isinstance(data, list):
            for item in data:
                paths.extend(find_paths_in_meta(item))
        elif isinstance(data, str) and "/" in data:
            paths.append(data)
        return paths

    discovered_paths = find_paths_in_meta(meta_content)
    discovered_paths.append("meta.yaml")

    return [
        intent_dir / p
        for p in set(discovered_paths)
        if not any(ign in p for ign in INTENT_IGNORE_PATTERNS)
    ]


def _get_docs_files() -> List[Path]:
    """Discovers and returns a list of all human-readable documentation files."""
    root_dir = settings.REPO_PATH
    scan_files = [
        root_dir / "README.md",
        root_dir / "CONTRIBUTING.md",
        root_dir / "SECURITY.md",
    ]
    docs_dir = root_dir / "docs"

    found_files: Set[Path] = {f for f in scan_files if f.exists()}

    if docs_dir.is_dir():
        for md_file in docs_dir.rglob("*.md"):
            if not any(ignored in md_file.parts for ignored in DOCS_IGNORE_DIRS):
                found_files.add(md_file)

    return list(found_files)


def _orchestrate_review(
    bundle_name: str,
    prompt_filename: str,
    file_gatherer_fn,
    output_path: Path,
    no_send: bool,
):
    """Generic orchestrator for all review commands."""
    log.info(f"🤖 Orchestrating review for: {bundle_name}...")

    prompt_path = settings.MIND / "prompts" / prompt_filename
    if not prompt_path.exists():
        log.error(f"❌ Review prompt not found at {prompt_path}. Cannot proceed.")
        raise typer.Exit(code=1)
    review_prompt_template = prompt_path.read_text(encoding="utf-8")
    log.info(f"   -> Loaded review prompt: {prompt_filename}")

    log.info("   -> Bundling files for review...")
    files_to_bundle = file_gatherer_fn()
    bundle_content = _get_bundle_content(files_to_bundle, settings.REPO_PATH)
    log.info(f"   -> Bundled {len(files_to_bundle)} files.")

    bundle_output_path = Path("reports") / f"{bundle_name}_bundle.txt"
    bundle_output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_output_path.write_text(bundle_content, encoding="utf-8")
    log.info(f"   -> Saved review bundle to: {bundle_output_path}")

    final_prompt = f"{review_prompt_template}\n\n{bundle_content}"

    if no_send:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(final_prompt, encoding="utf-8")
        log.info(f"✅ Full prompt bundle for manual review saved to: {output_path}")
        raise typer.Exit()

    log.info("   -> Sending bundle to LLM for analysis. This may take a moment...")
    cognitive_service = CognitiveService(settings.REPO_PATH)
    reviewer = cognitive_service.get_client_for_role("SecurityAnalyst")
    review_feedback = reviewer.make_request(
        final_prompt, user_id=f"{bundle_name}_reviewer"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review_feedback, encoding="utf-8")
    log.info(f"✅ Successfully received feedback and saved to: {output_path}")
    typer.secho(
        f"\n--- {bundle_name.replace('_', ' ').title()} Review Summary ---", bold=True
    )
    typer.echo(review_feedback)


# CAPABILITY: constitutional_peer_review
def peer_review(
    output: Path = typer.Option(
        Path("reports/constitutional_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
):
    """Audits the machine-readable constitution (.intent files) for clarity and consistency."""
    _orchestrate_review(
        bundle_name="constitutional",
        prompt_filename="constitutional_review.prompt",
        file_gatherer_fn=_get_constitutional_files,
        output_path=output,
        no_send=no_send,
    )


# CAPABILITY: docs.clarity_audit
def docs_clarity_audit(
    output: Path = typer.Option(
        Path("reports/docs_clarity_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
):
    """Audits the human-readable documentation (.md files) for conceptual clarity."""
    _orchestrate_review(
        bundle_name="docs_clarity",
        prompt_filename="docs_clarity_review.prompt",
        file_gatherer_fn=_get_docs_files,
        output_path=output,
        no_send=no_send,
    )


# CAPABILITY: code.peer_review
def code_review(
    file_path: Path = typer.Argument(
        ...,
        help="The relative path to the source code file to be reviewed.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
):
    """Submits a source file to an AI expert for a peer review and improvement suggestions."""
    log.info(
        f"🤖 Submitting '{file_path.relative_to(settings.REPO_PATH)}' for AI peer review..."
    )
    console = Console()

    try:
        source_code = file_path.read_text(encoding="utf-8")
        prompt_path = settings.MIND / "prompts" / "code_peer_review.prompt"
        review_prompt_template = prompt_path.read_text(encoding="utf-8")

        final_prompt = f"{review_prompt_template}\n\n```python\n{source_code}\n```"

        with console.status(
            "[bold green]Asking AI expert for review...[/bold green]", spinner="dots"
        ):
            cognitive_service = CognitiveService(settings.REPO_PATH)
            reviewer_client = cognitive_service.get_client_for_role("CodeReviewer")
            review_feedback = reviewer_client.make_request(
                final_prompt, user_id="code_review_operator"
            )

        console.print(
            Panel("AI Peer Review Complete", style="bold green", expand=False)
        )
        console.print(Markdown(review_feedback))

    except FileNotFoundError:
        log.error(f"❌ Error: File not found at '{file_path}'")
        raise typer.Exit(code=1)
    except Exception as e:
        log.error(
            f"❌ An unexpected error occurred during peer review: {e}", exc_info=True
        )
        raise typer.Exit(code=1)


def register(app: typer.Typer):
    """Registers the 'review' command group and its subcommands."""
    review_app = typer.Typer(help="Tools for constitutional and documentation review.")
    app.add_typer(review_app, name="review")

    review_app.command("constitution")(peer_review)
    review_app.command("docs")(docs_clarity_audit)
    review_app.command("code")(code_review)
