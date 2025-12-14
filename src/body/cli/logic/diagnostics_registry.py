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


# ID: 3a8ecff4-54d8-4fe1-8977-6c00d694db6f
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
        logger.error("%s CRITICAL errors found:", len(errors))
        for f in errors:
            logger.error("  %s", f)
    if warnings := [f for f in findings if f.severity == AuditSeverity.WARNING]:
        logger.warning("%s warnings found:", len(warnings))
        for f in warnings:
            logger.warning("  %s", f)
    raise typer.Exit(code=1 if errors else 0)


# ID: 67db4c4d-4483-4d71-9044-a1464ae3a4b2
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
        logger.error("CLI registry schema not found: %s", schema_path)
        raise typer.Exit(1)
    registry_content = registry_path.read_text("utf-8")
    registry = yaml.safe_load(registry_content) or {}
    schema_content = schema_path.read_text(encoding="utf-8")
    schema = json.loads(schema_content)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(registry), key=lambda e: e.path)
    if errors:
        logger.error("CLI registry failed validation against %s", schema_rel)
        for idx, err in enumerate(errors, 1):
            loc = "/".join(map(str, err.path)) or "(root)"
            logger.error("  {idx}. at %s: {err.message}", loc)
        raise typer.Exit(1)
    logger.info("CLI registry is valid: %s", registry_rel)


# ID: 03edb3b5-ca71-411e-8c90-5249d29a9543
def check_legacy_tags(ctx: typer.Context):
    """Runs only the LegacyTagCheck to find obsolete capability tags."""
    core_context: CoreContext = ctx.obj
    logger.info("Running standalone legacy tag check...")
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
