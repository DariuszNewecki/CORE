# src/cli/commands/cli_utils.py
"""
Provides centralized, reusable utilities for standardizing the console output
and execution of all `core-admin` commands.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import typer
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from rich.console import Console

from core.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.cli_utils")
console = Console()


def _run_poetry_command(description: str, command: list[str]):
    """Helper to run a command via Poetry, log it, and handle errors."""
    POETRY_EXECUTABLE = shutil.which("poetry")
    if not POETRY_EXECUTABLE:
        log.error("❌ Could not find 'poetry' executable in your PATH.")
        raise typer.Exit(code=1)

    typer.secho(f"\n{description}", bold=True)
    full_command = [POETRY_EXECUTABLE, "run", *command]
    try:
        result = subprocess.run(
            full_command, check=True, text=True, capture_output=True
        )
        if result.stdout:
            console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]{result.stderr}[/yellow]")
    except subprocess.CalledProcessError as e:
        log.error(f"\n❌ Command failed: {' '.join(full_command)}")
        if e.stdout:
            console.print(e.stdout)
        if e.stderr:
            console.print(f"[bold red]{e.stderr}[/bold red]")
        raise typer.Exit(code=1)


# ID: 76d0313a-1d12-4ea2-9c98-e1d44283bb86
async def find_test_file_for_capability_async(capability_key: str) -> Optional[Path]:
    """
    Asynchronously finds the test file corresponding to a given capability key.
    """
    log.debug(f"Searching for test file for capability: '{capability_key}'")
    try:
        knowledge_service = KnowledgeService(settings.REPO_PATH)
        graph = await knowledge_service.get_graph()
        symbols = graph.get("symbols", {})

        source_file_str = None
        for symbol in symbols.values():
            if symbol.get("key") == capability_key:
                source_file_str = symbol.get("file_path")
                break

        if not source_file_str:
            log.warning(f"Capability '{capability_key}' not found in knowledge graph.")
            return None

        p = Path(source_file_str)
        test_file_path = (
            settings.REPO_PATH / "tests" / p.relative_to("src")
        ).with_name(f"test_{p.name}")

        if test_file_path.exists():
            log.debug(f"Found corresponding test file at: {test_file_path}")
            return test_file_path
        else:
            log.warning(f"Conventional test file not found at: {test_file_path}")
            return None
    except Exception as e:
        log.error(f"Error processing knowledge graph: {e}")
        return None


# ID: 2c1e24f9-42a8-4851-92da-c0276e902551
def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Loads a YAML file safely."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# ID: 8400dcf6-6bea-4d10-9dd3-4d07416f0366
def save_yaml_file(path: Path, data: Dict[str, Any]) -> None:
    """Saves data to a YAML file with consistent sorting."""
    path.write_text(yaml.dump(data, sort_keys=True), encoding="utf-8")


# ID: ae41777a-644b-4dc7-8f08-f577060af15b
def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads the operator's private key."""
    key_path = settings.KEY_STORAGE_DIR / "private.key"
    if not key_path.exists():
        log.error(
            "❌ Private key not found. Please run 'core-admin keygen' to create one."
        )
        raise typer.Exit(code=1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


# ID: eebbca97-f3ba-46f0-a6dd-af189bfaf93c
def archive_rollback_plan(proposal_name: str, proposal: Dict[str, Any]) -> None:
    """Archives a proposal's rollback plan upon approval."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return
    rollbacks_dir = settings.MIND / "constitution" / "rollbacks"
    rollbacks_dir.mkdir(parents=True, exist_ok=True)
    archive_path = (
        rollbacks_dir
        / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{proposal_name}.json"
    )
    archive_path.write_text(
        json.dumps(
            {
                "proposal_name": proposal_name,
                "target_path": proposal.get("target_path"),
                "justification": proposal.get("justification"),
                "rollback_plan": rollback_plan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(f"📖 Rollback plan archived to {archive_path}")


# ID: 3c3a57ba-7b53-42ab-b544-ffe0fb9f6f24
def should_fail(report: dict, fail_on: str) -> bool:
    """
    Determines if the CLI should exit with an error code based on the drift
    report and the specified fail condition.
    """
    if fail_on == "missing":
        return bool(report.get("missing_in_code"))
    if fail_on == "undeclared":
        return bool(report.get("undeclared_in_manifest"))
    return bool(
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )
