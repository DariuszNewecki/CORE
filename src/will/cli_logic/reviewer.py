# src/will/cli_logic/reviewer.py
# ID: cli.logic.reviewer
"""
Provides commands for AI-powered review of the constitution, documentation, and source code files.
Refactored to comply with Agent I/O policies and Async-Native architecture.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.utils.constitutional_parser import get_all_constitutional_paths
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
console = Console()
DOCS_IGNORE_DIRS = {"assets", "archive", "migrations", "examples"}


async def _get_bundle_content(files_to_bundle: list[Path], root_dir: Path) -> str:
    """Read multiple files and bundle them into a context string."""
    bundle_parts = []
    for file_path in sorted(list(files_to_bundle)):
        if file_path.exists() and file_path.is_file():
            try:
                # Use FileHandler for safe reading
                content = await FileHandler.read_content(file_path)
                rel_path = file_path.resolve().relative_to(root_dir.resolve())
                bundle_parts.append(f"--- START OF FILE ./{rel_path} ---\n")
                bundle_parts.append(content)
                bundle_parts.append(f"\n--- END OF FILE ./{rel_path} ---\n\n")
            except ValueError:
                logger.warning(
                    "Could not determine relative path for %s. Skipping.", file_path
                )
            except Exception as e:
                logger.warning("Failed to read file %s: %s", file_path, e)
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


async def _orchestrate_review(
    bundle_name: str,
    prompt_key: str,
    file_gatherer_fn,
    output_path: Path,
    no_send: bool,
) -> None:
    logger.info("🤖 Orchestrating review for: %s...", bundle_name)
    try:
        prompt_path = settings.get_path(f"mind.prompts.{prompt_key}")
        review_prompt_template = await FileHandler.read_content(prompt_path)
    except Exception as e:
        logger.error(
            "❌ Review prompt '%s' not found or readable. Error: %s", prompt_key, e
        )
        raise typer.Exit(code=1)

    logger.info("   -> Loaded review prompt: %s", prompt_key)
    logger.info("   -> Bundling files for review...")

    files_to_bundle = file_gatherer_fn()
    bundle_content = await _get_bundle_content(files_to_bundle, settings.REPO_PATH)

    logger.info("   -> Bundled %s files.", len(files_to_bundle))

    bundle_output_path = settings.REPO_PATH / "reports" / f"{bundle_name}_bundle.txt"
    await FileHandler.ensure_parent_dir(bundle_output_path)
    await FileHandler.write_content(bundle_output_path, bundle_content)

    logger.info("   -> Saved review bundle to: %s", bundle_output_path)

    final_prompt = f"{review_prompt_template}\n\n{bundle_content}"

    if no_send:
        await FileHandler.ensure_parent_dir(output_path)
        await FileHandler.write_content(output_path, final_prompt)
        logger.info("✅ Full prompt bundle for manual review saved to: %s", output_path)
        # We don't raise Exit here to keep it composable, just return
        return

    logger.info("   -> Sending bundle to LLM for analysis. This may take a moment...")

    cognitive_service = CognitiveService(settings.REPO_PATH)
    reviewer = cognitive_service.get_client_for_role("SecurityAnalyst")

    # ID: 3b45b426-4966-45d9-9500-5faa0c8a4192
    review_feedback = await reviewer.make_request_async(
        final_prompt, user_id=f"{bundle_name}_reviewer"
    )

    await FileHandler.ensure_parent_dir(output_path)
    await FileHandler.write_content(output_path, review_feedback)

    logger.info("✅ Successfully received feedback and saved to: %s", output_path)
    logger.info("\n--- %s Review Summary ---", bundle_name.replace("_", " ").title())

    # We use console.print instead of logger for Markdown rendering
    console.print(Markdown(review_feedback))


# ID: b2729014-bda7-41fb-82b4-7093610495ee
async def peer_review(
    output: Path = typer.Option(
        Path("reports/constitutional_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
) -> None:
    """Audits the machine-readable constitution (.intent files) for clarity and consistency."""
    await _orchestrate_review(
        "constitutional",
        "constitutional_review",
        _get_constitutional_files,
        output,
        no_send,
    )


# ID: 46cc1fc6-2617-4448-9840-ec9eb8cdf64a
async def docs_clarity_audit(
    output: Path = typer.Option(
        Path("reports/docs_clarity_review.md"), "--output", "-o"
    ),
    no_send: bool = typer.Option(False, "--no-send"),
) -> None:
    """Audits the human-readable documentation (.md files) for conceptual clarity."""
    await _orchestrate_review(
        "docs_clarity", "docs_clarity_review", _get_docs_files, output, no_send
    )


# ID: 30a6ecd2-6d50-41a8-8e57-f5c511aea291
async def code_review(
    file_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, resolve_path=True
    ),
) -> None:
    """Submits a source file to an AI expert for a peer review and improvement suggestions."""
    logger.info(
        "🤖 Submitting '%s' for AI peer review...",
        file_path.relative_to(settings.REPO_PATH),
    )
    try:
        source_code = await FileHandler.read_content(file_path)
        prompt_path = settings.get_path("mind.prompts.code_peer_review")
        review_prompt_template = await FileHandler.read_content(prompt_path)

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

        logger.info(Panel("AI Peer Review Complete", style="bold green", expand=False))
        console.print(Markdown(review_feedback))

    except FileNotFoundError:
        logger.error("❌ Error: File not found at '%s'", file_path)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(
            "❌ An unexpected error occurred during peer review: %s",
            e,
            exc_info=True,
        )
        raise typer.Exit(code=1)
