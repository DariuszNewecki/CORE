# src/body/cli/logic/diagnostics_registry.py
"""
Logic for auditing the CLI registry and domain manifests.
"""

from __future__ import annotations

import json

import jsonschema
import typer
import yaml
from mind.governance.checks.domain_placement import DomainPlacementCheck
from mind.governance.checks.legacy_tag_check import LegacyTagCheck
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditSeverity

logger = getLogger(__name__)


# ID: d90abaa5-8336-4f11-bd52-8d1088f037da
def manifest_hygiene(ctx: typer.Context):
    """Checks for misplaced capabilities in domain manifests."""
    core_context: CoreContext = ctx.obj
    check = DomainPlacementCheck(core_context.auditor_context)
    findings = check.execute()
    if not findings:
        logger.info("All capabilities correctly placed in domain manifests")
        raise typer.Exit(code=0)
    errors = [f for f in findings if f.severity == AuditSeverity.ERROR]
    if errors:
        logger.error(f"{len(errors)} CRITICAL errors found:")
        for f in errors:
            logger.error(f"  {f}")
    if warnings := [f for f in findings if f.severity == AuditSeverity.WARNING]:
        logger.warning(f"{len(warnings)} warnings found:")
        for f in warnings:
            logger.warning(f"  {f}")
    raise typer.Exit(code=1 if errors else 0)


# ID: d0f4af61-2e34-4c98-989e-1b9dd9214e31
def cli_registry():
    """Validates the CLI registry against its constitutional schema."""
    meta_content = (settings.REPO_PATH / ".intent" / "meta.yaml").read_text("utf-8")
    meta = yaml.safe_load(meta_content) or {}
    knowledge = meta.get("mind", {}).get("knowledge", {})
    schemas = meta.get("charter", {}).get("schemas", {})
    registry_rel = knowledge.get("cli_registry", "mind/knowledge/cli_registry.yaml")
    schema_rel = schemas.get(
        "cli_registry_schema", "charter/schemas/cli_registry_schema.json"
    )

    registry_path = (settings.REPO_PATH / registry_rel).resolve()
    schema_path = (settings.REPO_PATH / schema_rel).resolve()

    if not registry_path.exists():
        logger.info(
            "Legacy CLI registry not found (this is expected after SSOT migration)."
        )
        return

    if not schema_path.exists():
        logger.error(f"CLI registry schema not found: {schema_path}")
        raise typer.Exit(1)

    registry_content = registry_path.read_text("utf-8")
    registry = yaml.safe_load(registry_content) or {}
    schema_content = schema_path.read_text(encoding="utf-8")
    schema = json.loads(schema_content)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: e.path)
    if errors:
        logger.error(f"CLI registry failed validation against {schema_rel}")
        for idx, err in enumerate(errors, 1):
            loc = "/".join(map(str, err.path)) or "(root)"
            logger.error(f"  {idx}. at {loc}: {err.message}")
        raise typer.Exit(1)
    logger.info(f"CLI registry is valid: {registry_rel}")


# ID: de787795-39e8-414a-9ea7-bd3d4bf22ef6
def check_legacy_tags(ctx: typer.Context):
    """Runs only the LegacyTagCheck to find obsolete capability tags."""
    core_context: CoreContext = ctx.obj

    logger.info("Running standalone legacy tag check...")
    check = LegacyTagCheck(core_context.auditor_context)
    findings = check.execute()
    if not findings:
        logger.info("Success! No legacy tags found.")
        return

    logger.error(f"Found {len(findings)} instance(s) of legacy tags:")
    for finding in findings:
        logger.error(
            f"  File: {finding.file_path}, Line: {finding.line_number}, Message: {finding.message}"
        )
    raise typer.Exit(code=1)
