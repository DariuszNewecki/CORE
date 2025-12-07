# src/will/cli_logic/reviewer.py

"""
Provides commands for AI-powered review of the constitution, documentation, and source code files.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from shared.config import settings
from shared.logger import getLogger
from shared.utils.constitutional_parser import get_all_constitutional_paths
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
console = Console()
DOCS_IGNORE_DIRS = {"assets", "archive", "migrations", "examples"}


def _get_bundle_content(files_to_bundle: list[Path], root_dir: Path) -> str:
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
                logger.warning(
                    f"Could not determine relative path for {file_path}. Skipping."
                )
    return "".join(bundle_parts)


def _get_constitutional_files() -> list[Path]:
    """
    Discovers all constitutional files by parsing meta.yaml via the settings object.
    """
    meta_content = settings._meta_config
    relative_paths = get_all_constitutional_paths(meta_content, settings.MIND)
    return [settings.REPO_PATH / p for p in relative_paths]


def _get_docs_files() -> list[Path]:
    root_dir = settings.REPO_PATH
    scan_files = [root_dir / "README.md", root_dir / "CONTRIBUTING.md"]
    docs_dir = root_dir / "docs"
    found_files: set[Path] = {f for f in scan_files if f.exists()}
    if docs_dir.is_dir():
        for md_file in docs_dir.rglob("*.md"):
            if not any(ignored in md_file.parts for ignored in DOCS_IGNORE_DIRS):
                found_files.add(md_file)
    return list(found_files)


def _orchestrate_review(
    bundle_name: str,
    prompt_key: str,
    file_gatherer_fn,
    output_path: Path,
    no_send: bool,
):
    logger.info("🤖 Orchestrating review for: %s...", bundle_name)
    try:
        prompt_path = settings.get_path(f"mind.prompts.{prompt_key}")
        review_prompt_template = prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(
            f"❌ Review prompt '{prompt_key}' not found in meta.yaml. Cannot proceed."
        )
        raise typer.Exit(code=1)
    logger.info("   -> Loaded review prompt: %s", prompt_key)
    logger.info("   -> Bundling files for review...")
    files_to_bundle = file_gatherer_fn()
    bundle_content = _get_bundle_content(files_to_bundle, settings.REPO_PATH)
    logger.info(f"   -> Bundled {len(files_to_bundle)} files.")
    bundle_output_path = settings.REPO_PATH / "reports" / f"{bundle_name}_bundle.txt"
    bundle_output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_output_path.write_text(bundle_content, encoding="utf-8")
    logger.info("   -> Saved review bundle to: %s", bundle_output_path)
    final_prompt = f"{review_prompt_template}\n\n{bundle_content}"
    if no_send:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(final_prompt, encoding="utf-8")
        logger.info("✅ Full prompt bundle for manual review saved to: %s", output_path)
        raise typer.Exit()
    logger.info("   -> Sending bundle to LLM for analysis. This may take a moment...")
    cognitive_service = CognitiveService(settings.REPO_PATH)
    reviewer = cognitive_service.get_client_for_role("SecurityAnalyst")

    # ID: fcd538e0-a244-4d3d-8219-b65a4920453c
    async def run_async_review():
        return await reviewer.make_request_async(
            final_prompt, user_id=f"{bundle_name}_reviewer"
        )

    review_feedback = asyncio.run(run_async_review())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review_feedback, encoding="utf-8")
    logger.info("✅ Successfully received feedback and saved to: %s", output_path)
    logger.info(f"\n--- {bundle_name.replace('_', ' ').title()} Review Summary ---")
    logger.info(Markdown(review_feedback))


# ID: 9b8c0610-8aa8-4442-9ee4-3d00a9c5d43d
def peer_review(
    output: Path = typer.Option(
        Path("reports/constitutional_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
):
    """Audits the machine-readable constitution (.intent files) for clarity and consistency."""
    _orchestrate_review(
        "constitutional",
        "constitutional_review",
        _get_constitutional_files,
        output,
        no_send,
    )


# ID: 5cf671e5-cec3-4a99-819f-8247d3bb54d0
def docs_clarity_audit(
    output: Path = typer.Option(
        Path("reports/docs_clarity_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
):
    """Audits the human-readable documentation (.md files) for conceptual clarity."""
    _orchestrate_review(
        "docs_clarity", "docs_clarity_review", _get_docs_files, output, no_send
    )


# ID: eb28c6be-2ddb-4593-b49e-e74aa518c02a
def code_review(
    file_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, resolve_path=True
    ),
):
    """Submits a source file to an AI expert for a peer review and improvement suggestions."""

    async def _async_code_review():
        logger.info(
            f"🤖 Submitting '{file_path.relative_to(settings.REPO_PATH)}' for AI peer review..."
        )
        try:
            source_code = file_path.read_text(encoding="utf-8")
            prompt_path = settings.get_path("mind.prompts.code_peer_review")
            review_prompt_template = prompt_path.read_text(encoding="utf-8")
            final_prompt = f"{review_prompt_template}\n\n```python\n{source_code}\n```"
            with console.status(
                "[bold green]Asking AI expert for review...[/bold green]",
                spinner="dots",
            ):
                cognitive_service = CognitiveService(settings.REPO_PATH)
                reviewer_client = cognitive_service.get_client_for_role("CodeReviewer")
                review_feedback = await reviewer_client.make_request_async(
                    final_prompt, user_id="code_review_operator"
                )
            logger.info(
                Panel("AI Peer Review Complete", style="bold green", expand=False)
            )
            logger.info(Markdown(review_feedback))
        except FileNotFoundError:
            logger.error("❌ Error: File not found at '%s'", file_path)
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error(
                f"❌ An unexpected error occurred during peer review: {e}",
                exc_info=True,
            )
            raise typer.Exit(code=1)

    asyncio.run(_async_code_review())
