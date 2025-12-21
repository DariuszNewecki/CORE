# src/body/cli/logic/diagnostics_registry.py

"""
Logic for auditing domain manifests and (optionally) legacy CLI registry artifacts.

Important:
- This module must NOT reference deprecated legacy artifact filenames directly
  (knowledge.limited_legacy_access). If the legacy registry still exists, its
  location must be provided via .intent/meta.yaml and handled only when present.
"""

from __future__ import annotations

import json

import jsonschema
import typer
import yaml

from mind.governance.check_registry import check_exists, get_check
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditSeverity


logger = getLogger(__name__)


# ID: 3a8ecff4-54d8-4fe1-8977-6c00d694db6f
def manifest_hygiene(ctx: typer.Context) -> None:
    """
    Checks for misplaced capabilities in domain manifests.

    NOTE: DomainPlacementCheck was removed as obsolete (references deleted project_structure.yaml).
    This function now gracefully handles its absence.
    """
    core_context: CoreContext = ctx.obj

    # Check if DomainPlacementCheck exists (it was deleted)
    if not check_exists("DomainPlacementCheck"):
        logger.info(
            "DomainPlacementCheck not available (obsolete check removed). "
            "Domain placement validation moved to database."
        )
        raise typer.Exit(code=0)

    # If somehow it still exists, run it
    DomainPlacementCheck = get_check("DomainPlacementCheck")
    check = DomainPlacementCheck(core_context.auditor_context)
    findings = check.execute()

    if not findings:
        logger.info("All capabilities correctly placed in domain manifests")
        raise typer.Exit(code=0)

    errors = [f for f in findings if f.severity == AuditSeverity.ERROR]
    if errors:
        logger.error("%s CRITICAL errors found:", len(errors))
        for f in errors:
            logger.error("  %s", f)

    warnings = [f for f in findings if f.severity == AuditSeverity.WARNING]
    if warnings:
        logger.warning("%s warnings found:", len(warnings))
        for f in warnings:
            logger.warning("  %s", f)

    raise typer.Exit(code=1 if errors else 0)


def _load_intent_meta() -> dict:
    meta_path = settings.REPO_PATH / ".intent" / "meta.yaml"
    if not meta_path.exists():
        logger.error("Missing .intent/meta.yaml: %s", meta_path)
        raise typer.Exit(code=1)
    try:
        return yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.error("Failed to parse .intent/meta.yaml: %s", e)
        raise typer.Exit(code=1)


def _resolve_from_meta(meta: dict, *keys: str) -> str | None:
    cur: object = meta
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur if isinstance(cur, str) and cur.strip() else None


# ID: 67db4c4d-4483-4d71-9044-a1464ae3a4b2
def cli_registry() -> None:
    """
    Validates the *legacy* CLI registry YAML (if still present) against its schema.

    Post-SSOT migration behavior:
    - If meta.yaml does not declare a legacy registry path, this check is skipped.
    - If meta.yaml declares one, we validate it (useful during transition cleanup).
    """
    meta = _load_intent_meta()

    registry_rel = _resolve_from_meta(meta, "mind", "knowledge", "cli_registry")
    schema_rel = _resolve_from_meta(meta, "charter", "schemas", "cli_registry_schema")

    if not registry_rel:
        logger.info(
            "No legacy CLI registry declared in meta.yaml; skipping validation."
        )
        return
    if not schema_rel:
        logger.warning(
            "No CLI registry schema declared in meta.yaml; skipping validation."
        )
        return

    registry_path = (settings.REPO_PATH / registry_rel).resolve()
    schema_path = (settings.REPO_PATH / schema_rel).resolve()

    if not registry_path.exists():
        logger.info("Legacy CLI registry path not found on disk: %s", registry_rel)
        return
    if not schema_path.exists():
        logger.error("CLI registry schema not found: %s", schema_path)
        raise typer.Exit(code=1)

    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: list(e.path))

    if errors:
        logger.error("CLI registry failed validation against schema: %s", schema_rel)
        for idx, err in enumerate(errors, 1):
            loc = "/".join(map(str, err.path)) or "(root)"
            logger.error("  %s. at %s: %s", idx, loc, err.message)
        raise typer.Exit(code=1)

    logger.info("Legacy CLI registry is valid: %s", registry_rel)


# ID: 03edb3b5-ca71-411e-8c90-5249d29a9543
def check_legacy_tags(ctx: typer.Context) -> None:
    """Runs only the LegacyTagCheck to find obsolete capability tags."""
    core_context: CoreContext = ctx.obj
    logger.info("Running standalone legacy tag check...")

    # Dynamic check lookup
    LegacyTagCheck = get_check("LegacyTagCheck")
    check = LegacyTagCheck(core_context.auditor_context)
    findings = check.execute()

    if not findings:
        logger.info("Success! No legacy tags found.")
        return

    logger.error("Found %s instance(s) of legacy tags:", len(findings))
    for finding in findings:
        logger.error(
            "  File: %s, Line: %s, Message: %s",
            finding.file_path,
            finding.line_number,
            finding.message,
        )
    raise typer.Exit(code=1)
