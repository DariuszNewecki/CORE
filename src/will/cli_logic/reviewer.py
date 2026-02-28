# src/will/cli_logic/reviewer.py
# ID: 50f03dc0-1305-4bac-bf89-0b3f85055173
"""
Provides commands for AI-powered review of the constitution, documentation, and source code files.
Refactored to comply with Agent I/O policies and Async-Native architecture.

Constitutional Alignment:
- Uses CoreContext for dependency injection (no direct settings import)
- Uses FileService from Body layer for all file operations
- Will layer orchestrates but does not execute
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


# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567801
async def _get_bundle_content(
    files_to_bundle: list[Path], root_dir: Path, file_service: FileService
) -> str:
    """Read multiple files and bundle them into a context string."""
    bundle_parts = []
    for file_path in sorted(list(files_to_bundle)):
        if file_path.exists() and file_path.is_file():
            try:
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


# ID: b2c3d4e5-f6a7-8901-bcde-f01234567802
def _get_constitutional_files() -> list[Path]:
    """Return all files indexed as constitutional policies."""
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    return [Path(p.file_path) for p in repo.list_policies()]


# ID: c3d4e5f6-a7b8-9012-cdef-012345678803
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


# ID: d4e5f6a7-b8c9-0123-defa-012345678804
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

    Args:
        context: CoreContext with injected dependencies
        review_type: Type of review (for logging)
        prompt_key: Key to retrieve prompt from mind prompts
        files_getter: Function to get files to review
        output_path: Optional path to write output
        no_send: If True, don't send to AI, just bundle
    """
    logger.info("🤖 Preparing %s review...", review_type)

    file_service = getattr(context, "file_service", None)
    if file_service is None:
        file_service = FileService(context.repo_path)

    if files_getter == _get_constitutional_files:
        files_to_bundle = files_getter()
    else:
        files_to_bundle = files_getter(context)

    if not files_to_bundle:
        logger.warning("No files found for %s review", review_type)
        raise typer.Exit(code=1)

    logger.info("Found %d files to review", len(files_to_bundle))

    bundled_content = await _get_bundle_content(
        files_to_bundle, context.repo_path, file_service
    )

    if no_send:
        logger.info("--no-send flag detected. Writing bundle to output file...")
        if not output_path:
            output_path = context.repo_path / "work" / f"{review_type}_bundle.txt"

        file_service.ensure_dir("work")
        rel_output = str(output_path.relative_to(context.repo_path))
        file_service.write_file(rel_output, bundled_content)
        logger.info("Bundle written to: %s", output_path)
        return

    prompt_path = context.path_resolver.get_prompt_path(prompt_key)
    if not prompt_path.exists():
        logger.error("Prompt template not found: %s", prompt_path)
        raise typer.Exit(code=1)

    rel_prompt = str(prompt_path.relative_to(context.repo_path))
    review_prompt_template = file_service.read_file(rel_prompt)

    if review_prompt_template is None:
        logger.error("Could not read prompt template: %s", prompt_path)
        raise typer.Exit(code=1)

    final_prompt = f"{review_prompt_template}\n\n{bundled_content}"

    with console.status(
        f"[bold green]Requesting {review_type} review from AI...[/bold green]",
        spinner="dots",
    ):
        cognitive_service = CognitiveService(context.repo_path)
        reviewer_client = cognitive_service.get_client_for_role("Reviewer")
        review_feedback = await reviewer_client.make_request_async(
            final_prompt, user_id=f"{review_type}_operator"
        )

    logger.info(
        Panel(
            f"{review_type.title()} Review Complete", style="bold green", expand=False
        )
    )
    console.print(Markdown(review_feedback))

    if output_path:
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
    """Submits a source file to an AI expert for a peer review and improvement suggestions."""
    logger.info(
        "🤖 Submitting '%s' for AI peer review...",
        file_path.relative_to(context.repo_path),
    )

    file_service = getattr(context, "file_service", None)
    if file_service is None:
        file_service = FileService(context.repo_path)

    try:
        rel_file = str(file_path.relative_to(context.repo_path))
        source_code = file_service.read_file(rel_file)

        if source_code is None:
            logger.error("❌ Error: Could not read file at '%s'", file_path)
            raise typer.Exit(code=1)

        prompt_path = context.path_resolver.get_prompt_path("code_peer_review")

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
