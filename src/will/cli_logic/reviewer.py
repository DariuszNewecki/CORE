# src/will/cli_logic/reviewer.py
# ID: cli.logic.reviewer
"""
Provides commands for AI-powered review of the constitution, documentation, and source code files.
Refactored to comply with Agent I/O policies and Async-Native architecture.

CONSTITUTIONAL COMPLIANCE:
- Uses CoreContext for dependency injection (no direct settings import)
- NO LONGER imports FileHandler - uses FileService from Body layer
- Will layer orchestrates but doesn't execute
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from body.services.file_service import FileService
from shared.context import CoreContext
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)
console = Console()
DOCS_IGNORE_DIRS = {"assets", "archive", "migrations", "examples"}


async def _get_bundle_content(
    files_to_bundle: list[Path], root_dir: Path, file_service: FileService
) -> str:
    """
    Read multiple files and bundle them into a context string.

    CONSTITUTIONAL FIX: Receives FileService parameter for file reading
    """
    bundle_parts = []
    for file_path in sorted(list(files_to_bundle)):
        if file_path.exists() and file_path.is_file():
            try:
                # CONSTITUTIONAL FIX: Use FileService for safe reading
                rel_path_str = str(file_path.relative_to(root_dir))
                content = file_service.read_file(rel_path_str)

                if content is None:
                    logger.warning("Could not read file: %s", file_path)
                    continue

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
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    # If the repo indexed it, it's a constitutional file.
    return [Path(p.file_path) for p in repo.list_policies()]


def _get_docs_files(context: CoreContext) -> list[Path]:
    """Gather documentation files (.md) from docs/ folder."""
    docs_dir = context.repo_path / "docs"
    if not docs_dir.exists():
        logger.warning("Docs directory not found at %s", docs_dir)
        return []

    md_files = []
    for md_file in docs_dir.rglob("*.md"):
        if any(ignored in md_file.parts for ignored in DOCS_IGNORE_DIRS):
            continue
        md_files.append(md_file)
    return md_files


async def _orchestrate_review(
    context: CoreContext,
    review_type: str,
    prompt_key: str,
    files_getter: callable,
    output_path: Path | None = None,
    no_send: bool = False,
) -> None:
    """
    Generic orchestration for AI-powered reviews.

    CONSTITUTIONAL FIX: Uses FileService from context for all file operations

    Args:
        context: CoreContext with injected dependencies
        review_type: Type of review (for logging)
        prompt_key: Key to retrieve prompt from mind prompts
        files_getter: Function to get files to review
        output_path: Optional path to write output
        no_send: If True, don't send to AI, just bundle
    """
    logger.info("🤖 Preparing %s review...", review_type)

    # CONSTITUTIONAL FIX: Get FileService from context or create one
    file_service = getattr(context, "file_service", None)
    if file_service is None:
        file_service = FileService(context.repo_path)

    # Get files based on review type
    if files_getter == _get_constitutional_files:
        files_to_bundle = files_getter()
    else:
        files_to_bundle = files_getter(context)

    if not files_to_bundle:
        logger.warning("No files found for %s review", review_type)
        raise typer.Exit(code=1)

    logger.info("Found %d files to review", len(files_to_bundle))

    # CONSTITUTIONAL FIX: Bundle file contents via FileService
    bundled_content = await _get_bundle_content(
        files_to_bundle, context.repo_path, file_service
    )

    if no_send:
        logger.info("--no-send flag detected. Writing bundle to output file...")
        if not output_path:
            output_path = context.repo_path / "work" / f"{review_type}_bundle.txt"

        # CONSTITUTIONAL FIX: Use FileService
        file_service.ensure_dir("work")
        rel_output = str(output_path.relative_to(context.repo_path))
        file_service.write_file(rel_output, bundled_content)
        logger.info("Bundle written to: %s", output_path)
        return

    # Load prompt template
    prompt_path = context.path_resolver.get_prompt_path(prompt_key)
    if not prompt_path.exists():
        logger.error("Prompt template not found: %s", prompt_path)
        raise typer.Exit(code=1)

    # CONSTITUTIONAL FIX: Use FileService to read prompt
    rel_prompt = str(prompt_path.relative_to(context.repo_path))
    review_prompt_template = file_service.read_file(rel_prompt)

    if review_prompt_template is None:
        logger.error("Could not read prompt template: %s", prompt_path)
        raise typer.Exit(code=1)

    final_prompt = f"{review_prompt_template}\n\n{bundled_content}"

    # Send to AI for review
    with console.status(
        f"[bold green]Requesting {review_type} review from AI...[/bold green]",
        spinner="dots",
    ):
        cognitive_service = CognitiveService(context.repo_path)
        reviewer_client = cognitive_service.get_client_for_role("Reviewer")
        review_feedback = await reviewer_client.make_request_async(
            final_prompt, user_id=f"{review_type}_operator"
        )

    # Present results
    logger.info(
        Panel(
            f"{review_type.title()} Review Complete", style="bold green", expand=False
        )
    )
    console.print(Markdown(review_feedback))

    # Optionally save output
    if output_path:
        # CONSTITUTIONAL FIX: Use FileService
        file_service.ensure_dir(str(output_path.parent.relative_to(context.repo_path)))
        rel_output = str(output_path.relative_to(context.repo_path))
        file_service.write_file(rel_output, review_feedback)
        logger.info("Review saved to: %s", output_path)


# ID: c4b1e7f2-8a5d-4e9c-b3f1-7c8d9e0a1b2c
async def constitutional_review(
    context: CoreContext,
    output: Path | None = typer.Option(None, "--output", "-o"),
    no_send: bool = typer.Option(False, "--no-send"),
) -> None:
    """Reviews the entire constitutional structure (.intent/) for clarity and consistency."""
    await _orchestrate_review(
        context,
        "constitutional",
        "constitutional_review",
        _get_constitutional_files,
        output,
        no_send,
    )


# ID: 5a7c8e3f-9b2d-4c1e-a6f7-8d9e0b1c2d3e
async def docs_review(
    context: CoreContext,
    output: Path | None = typer.Option(None, "--output", "-o"),
    no_send: bool = typer.Option(False, "--no-send"),
) -> None:
    """Reviews the project documentation for clarity, accuracy, and completeness."""
    await _orchestrate_review(
        context,
        "docs_clarity",
        "docs_clarity_review",
        _get_docs_files,
        output,
        no_send,
    )


# ID: 30a6ecd2-6d50-41a8-8e57-f5c511aea291
async def code_review(
    context: CoreContext,
    file_path: Path = typer.Argument(
        ..., exists=True, dir_okay=False, resolve_path=True
    ),
) -> None:
    """
    Submits a source file to an AI expert for a peer review and improvement suggestions.

    CONSTITUTIONAL FIX: Uses FileService for file reading
    """
    logger.info(
        "🤖 Submitting '%s' for AI peer review...",
        file_path.relative_to(context.repo_path),
    )

    # CONSTITUTIONAL FIX: Get FileService
    file_service = getattr(context, "file_service", None)
    if file_service is None:
        file_service = FileService(context.repo_path)

    try:
        # CONSTITUTIONAL FIX: Use FileService to read source code
        rel_file = str(file_path.relative_to(context.repo_path))
        source_code = file_service.read_file(rel_file)

        if source_code is None:
            logger.error("❌ Error: Could not read file at '%s'", file_path)
            raise typer.Exit(code=1)

        prompt_path = context.path_resolver.get_prompt_path("code_peer_review")

        # CONSTITUTIONAL FIX: Use FileService to read prompt
        rel_prompt = str(prompt_path.relative_to(context.repo_path))
        review_prompt_template = file_service.read_file(rel_prompt)

        if review_prompt_template is None:
            logger.error("❌ Error: Could not read prompt template")
            raise typer.Exit(code=1)

        final_prompt = f"{review_prompt_template}\n\n```python\n{source_code}\n```"

        with console.status(
            "[bold green]Asking AI expert for review...[/bold green]",
            spinner="dots",
        ):
            cognitive_service = CognitiveService(context.repo_path)
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
