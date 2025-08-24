# src/system/admin/reviewer.py
"""
Intent: Implements commands related to constitutional review and improvement.
This includes exporting the constitution for external analysis and orchestrating
an AI-powered peer review for both the machine-readable constitution and the
human-readable documentation.
"""

from pathlib import Path

import typer
import yaml

from core.cognitive_service import CognitiveService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.review")

# A set of files/patterns within .intent/ to ignore during the constitutional export.
INTENT_IGNORE_PATTERNS = {"proposals", "knowledge_graph.json", ".bak", ".example"}

# A set of directories to ignore when bundling human-readable documentation.
DOCS_IGNORE_DIRS = {"assets", "archive", "migrations", "examples"}


def _is_intent_ignored(path_str: str) -> bool:
    """Checks if a given .intent file path should be ignored."""
    return any(pattern in path_str for pattern in INTENT_IGNORE_PATTERNS)


def _get_constitutional_bundle_content() -> str:
    """Gathers and bundles the content of all machine-readable constitutional files."""
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
        if _is_intent_ignored(rel_path_str):
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
    """
    log.info("🏛️  Exporting constitutional bundle...")
    final_bundle = _get_constitutional_bundle_content()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(final_bundle, encoding="utf-8")
    log.info(f"✅ Successfully exported constitutional bundle to: {output}")


def peer_review(
    output: Path = typer.Option(
        Path("reports/constitutional_review.md"),
        "--output",
        "-o",
        help="The path to save the LLM's review or the bundled prompt.",
    ),
    no_send: bool = typer.Option(
        False,
        "--no-send",
        help="Prepare the full prompt bundle and save it without sending to the LLM.",
    ),
):
    """
    Orchestrates sending the constitutional bundle to an external LLM for critique.
    """
    if no_send:
        log.info(
            "🤖 Preparing constitutional bundle for manual review (no-send mode)..."
        )
    else:
        log.info("🤖 Orchestrating Constitutional Peer Review...")

    prompt_path = settings.MIND / "prompts" / "constitutional_review.prompt"
    if not prompt_path.exists():
        log.error(f"❌ Review prompt not found at {prompt_path}. Cannot proceed.")
        raise typer.Exit(code=1)
    review_prompt_template = prompt_path.read_text(encoding="utf-8")
    log.info("   -> Loaded review prompt from the constitution.")

    log.info("   -> Bundling the constitution for review...")
    bundle = _get_constitutional_bundle_content()
    final_prompt = f"{review_prompt_template}\n\n{bundle}"

    if no_send:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(final_prompt, encoding="utf-8")
        log.info(f"✅ Full prompt bundle for manual review saved to: {output}")
        raise typer.Exit()

    log.info(
        "   -> Sending bundle to external LLM for analysis. This may take a moment..."
    )
    cognitive_service = CognitiveService(settings.REPO_PATH)
    reviewer = cognitive_service.get_client_for_role("SecurityAnalyst")
    review_feedback = reviewer.make_request(
        final_prompt, user_id="constitutional_reviewer"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(review_feedback, encoding="utf-8")
    log.info(
        f"✅ Successfully received feedback from peer review and saved to: {output}"
    )
    typer.secho("\n--- Review Summary ---", bold=True)
    typer.echo(review_feedback)


# --- NEW CAPABILITY IMPLEMENTATION ---
# CAPABILITY: docs.clarity_audit
def docs_clarity_audit(
    output: Path = typer.Option(
        Path("reports/docs_clarity_review.md"),
        "--output",
        "-o",
        help="The path to save the LLM's documentation review.",
    ),
):
    """
    Bundles all human-facing documentation for a conceptual clarity review by an LLM.
    """
    log.info("🧐 Performing Human Clarity Audit on project documentation...")

    # 1. Load the specific prompt for this audit.
    prompt_path = settings.MIND / "prompts" / "docs_clarity_review.prompt"
    if not prompt_path.exists():
        log.error(
            f"❌ Clarity review prompt not found at {prompt_path}. Cannot proceed."
        )
        raise typer.Exit(code=1)
    review_prompt_template = prompt_path.read_text(encoding="utf-8")
    log.info("   -> Loaded clarity review prompt from the constitution.")

    # 2. Bundle all human-readable documentation (.md files).
    log.info("   -> Bundling all .md documentation files...")
    bundle_parts = []
    # Scan both the root and the docs directory for markdown files.
    scan_paths = [Path("."), Path("docs")]
    found_files = set()
    for p in scan_paths:
        for md_file in p.rglob("*.md"):
            # Exclude files in ignored directories
            if any(ignored in md_file.parts for ignored in DOCS_IGNORE_DIRS):
                continue
            if md_file not in found_files:
                content = md_file.read_text(encoding="utf-8")
                bundle_parts.append(f"--- START OF FILE ./{md_file} ---\n")
                bundle_parts.append(content)
                bundle_parts.append(f"\n--- END OF FILE ./{md_file} ---\n\n")
                found_files.add(md_file)

    docs_bundle = "".join(bundle_parts)
    log.info(f"   -> Bundled {len(found_files)} documentation files.")

    # 3. Combine them into the final prompt.
    final_prompt = f"{review_prompt_template}\n\n{docs_bundle}"

    # 4. Send to the LLM for review.
    log.info("   -> Sending documentation bundle to LLM for clarity analysis...")
    cognitive_service = CognitiveService(settings.REPO_PATH)
    # The 'SecurityAnalyst' role is a good generic choice for high-level analysis.
    reviewer = cognitive_service.get_client_for_role("SecurityAnalyst")
    review_feedback = reviewer.make_request(
        final_prompt, user_id="docs_clarity_auditor"
    )

    # 5. Save and display the feedback.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(review_feedback, encoding="utf-8")
    log.info(f"✅ Successfully received clarity review and saved to: {output}")
    typer.secho("\n--- Human Clarity Audit Summary ---", bold=True)
    typer.echo(review_feedback)


def register(app: typer.Typer):
    """Registers the 'review' command group and its subcommands."""
    review_app = typer.Typer(help="Tools for constitutional and documentation review.")
    app.add_typer(review_app, name="review")

    # Machine-readable constitution review
    review_app.command("constitution")(peer_review)
    review_app.command("export-constitution")(export_constitution)

    # Human-readable documentation review
    review_app.command("docs")(docs_clarity_audit)
