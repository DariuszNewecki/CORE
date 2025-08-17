# src/system/admin/reviewer.py
"""
Intent: Implements commands related to constitutional review and improvement.
This includes exporting the constitution for external analysis and orchestrating
an AI-powered peer review.
"""

from pathlib import Path

import typer
import yaml
from rich import print as rprint
from rich.panel import Panel

from core.clients import OrchestratorClient
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.review")

# A set of files/patterns within .intent/ to ignore during export.
IGNORE_PATTERNS = {"proposals", "knowledge_graph.json", ".bak", ".example"}


def _is_ignored(path_str: str) -> bool:
    """Checks if a given file path should be ignored based on IGNORE_PATTERNS."""
    return any(pattern in path_str for pattern in IGNORE_PATTERNS)


def _get_bundle_content() -> str:
    """Gathers and bundles the content of all constitutional files."""
    intent_dir = settings.MIND
    meta_path = intent_dir / "meta.yaml"
    if not meta_path.exists():
        log.error(
            f"❌ Critical file not found: {meta_path}. Cannot export constitution."
        )
        raise typer.Exit(code=1)

    meta_content = yaml.safe_load(meta_path.read_text())

    bundle_parts = []

    def find_paths_in_meta(data):
        """Recursively extracts all strings containing '/' from nested dictionaries, lists, or strings in `data`."""
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

    log.info(
        f"   -> Found {len(list(set(discovered_paths)))} constitutional files declared in meta.yaml."
    )

    for rel_path_str in sorted(list(set(discovered_paths))):
        if _is_ignored(rel_path_str):
            continue

        file_path = intent_dir / rel_path_str
        if file_path.exists() and file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            bundle_parts.append(f"--- START OF FILE .intent/{rel_path_str} ---\n")
            bundle_parts.append(content)
            bundle_parts.append(f"\n--- END OF FILE .intent/{rel_path_str} ---\n\n")

    return "".join(bundle_parts)


def export_constitution(
    output: Path = typer.Option(
        Path("reports/constitution_bundle.txt"),
        "--output",
        "-o",
        help="The path to save the exported constitutional bundle.",
    ),
):
    """
    Packages the full .intent/ directory into a single bundle for external analysis.
    This command reads the meta.yaml file to discover all constitutional files
    and concatenates them into a single, LLM-friendly text file.
    """
    log.info("🏛️  Exporting constitutional bundle...")
    final_bundle = _get_bundle_content()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(final_bundle, encoding="utf-8")
    log.info(f"✅ Successfully exported constitutional bundle to: {output}")


def peer_review(
    output: Path = typer.Option(
        Path("reports/constitutional_review.md"),
        "--output",
        "-o",
        help="The path to save the LLM's review.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Prepare the full prompt and print it to the console without sending to the LLM.",
    ),
):
    """
    Orchestrates sending the constitutional bundle to an external LLM for critique.
    """
    if dry_run:
        log.info(
            "🤖 Preparing constitutional prompt for manual review (dry-run mode)..."
        )
    else:
        log.info("🤖 Orchestrating Constitutional Peer Review...")

    # 1. Load the review prompt from the constitution itself.
    prompt_path = settings.MIND / "prompts" / "constitutional_review.prompt"
    if not prompt_path.exists():
        log.error(f"❌ Review prompt not found at {prompt_path}. Cannot proceed.")
        raise typer.Exit(code=1)
    review_prompt_template = prompt_path.read_text(encoding="utf-8")

    # 2. Export the constitutional bundle.
    log.info("   -> Bundling the constitution for review...")
    bundle = _get_bundle_content()

    # 3. Combine them into the final prompt.
    final_prompt = f"{review_prompt_template}\n\n{bundle}"

    # 4. If --dry-run is used, print and exit.
    if dry_run:
        rprint(
            Panel(
                final_prompt,
                title="[bold yellow]Final Prompt to be Sent[/bold yellow]",
                border_style="yellow",
            )
        )
        log.info("✅ Dry-run complete. No request was sent.")
        raise typer.Exit()

    # 5. Otherwise, send to the Orchestrator LLM.
    log.info(
        "   -> Sending bundle to external LLM for analysis. This may take a moment..."
    )

    orchestrator = OrchestratorClient()
    review_feedback = orchestrator.make_request(
        final_prompt, user_id="constitutional_reviewer"
    )

    # 6. Save the feedback.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(review_feedback, encoding="utf-8")

    log.info("✅ Successfully received feedback from peer review.")
    log.info(f"   -> Full review saved to: {output}")
    typer.secho("\n--- Review Summary ---", bold=True)
    typer.echo(review_feedback)


def register(app: typer.Typer):
    """Registers the 'review' command group and its subcommands."""
    review_app = typer.Typer(help="Tools for constitutional review and improvement.")
    app.add_typer(review_app, name="review")
    review_app.command("export")(export_constitution)
    review_app.command("peer-review")(peer_review)
