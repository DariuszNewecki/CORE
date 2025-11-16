# src/body/cli/logic/cli_utils.py

"""
Provides centralized, reusable utilities for standardizing the console output
and execution of all `core-admin` commands.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from rich.console import Console
from services.knowledge.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)
console = Console()


# ID: ebc07171-b4df-48cd-99b5-2bd8a06056d4
async def find_test_file_for_capability_async(capability_key: str) -> Path | None:
    """
    Asynchronously finds the test file corresponding to a given capability key.
    """
    logger.debug(f"Searching for test file for capability: '{capability_key}'")
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
            logger.warning(
                f"Capability '{capability_key}' not found in knowledge graph."
            )
            return None
        p = Path(source_file_str)
        test_file_path = (
            settings.REPO_PATH / "tests" / p.relative_to("src")
        ).with_name(f"test_{p.name}")
        if test_file_path.exists():
            logger.debug(f"Found corresponding test file at: {test_file_path}")
            return test_file_path
        else:
            logger.warning(f"Conventional test file not found at: {test_file_path}")
            return None
    except Exception as e:
        logger.error(f"Error processing knowledge graph: {e}")
        return None


# ID: 92607e4d-3537-4ea8-b04f-77c36b026171
def save_yaml_file(path: Path, data: dict[str, Any]) -> None:
    """Saves data to a YAML file with consistent sorting."""
    import yaml

    path.write_text(yaml.dump(data, sort_keys=True), encoding="utf-8")


# ID: d7abfcd7-d423-491c-aca5-4d48f4fc9355
def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Loads the operator's private key."""
    key_path = settings.KEY_STORAGE_DIR / "private.key"
    if not key_path.exists():
        logger.error(
            "❌ Private key not found. Please run 'core-admin keygen' to create one."
        )
        raise typer.Exit(code=1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


# ID: 44918a43-7049-42f8-9c07-64818cefc7d2
def archive_rollback_plan(proposal_name: str, proposal: dict[str, Any]) -> None:
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
    logger.info(f"📖 Rollback plan archived to {archive_path}")


# ID: 33632ec4-5afe-413e-b5ca-37153c5c2fa0
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
