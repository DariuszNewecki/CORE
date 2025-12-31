# src/body/cli/logic/diagnostics_registry.py

"""
Logic for auditing domain manifests and legacy artifacts.
Refactored to use the dynamic constitutional rule engine instead of deleted legacy check classes.
"""

from __future__ import annotations

import json

import jsonschema
import typer
import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.config import settings
from shared.context import CoreContext  # Fixed: Added missing import
from shared.logger import getLogger
from shared.models import AuditSeverity


logger = getLogger(__name__)


# ID: 3a8ecff4-54d8-4fe1-8977-6c00d694db6f
async def manifest_hygiene(ctx: typer.Context) -> None:
    """
    Checks for misplaced capabilities or structural drift in the knowledge base.
    Uses the 'knowledge.database_ssot' constitutional rule.
    """
    core_context: CoreContext = ctx.obj
    logger.info("🔍 Running manifest hygiene check (SSOT alignment)...")

    # 1. Initialize AuditorContext
    auditor_context = core_context.auditor_context or AuditorContext(settings.REPO_PATH)
    await auditor_context.load_knowledge_graph()

    # 2. Extract and find the SSOT rule
    all_rules = extract_executable_rules(auditor_context.policies)
    target_rule = next(
        (r for r in all_rules if r.rule_id == "knowledge.database_ssot"), None
    )

    if not target_rule:
        logger.warning(
            "Constitutional rule 'knowledge.database_ssot' not found. Skipping hygiene check."
        )
        return

    # 3. Execute and report
    findings = await execute_rule(target_rule, auditor_context)

    if not findings:
        logger.info("✅ All capabilities correctly placed and synchronized with DB.")
        return

    # Sort findings by severity
    errors = [f for f in findings if f.severity == AuditSeverity.ERROR]
    warnings = [f for f in findings if f.severity == AuditSeverity.WARNING]

    if errors:
        logger.error("❌ Found %s CRITICAL alignment errors:", len(errors))
        for f in errors:
            logger.error("  - %s", f.message)

    if warnings:
        logger.warning("⚠️  Found %s alignment warnings:", len(warnings))
        for f in warnings:
            logger.warning("  - %s", f.message)

    if errors:
        raise typer.Exit(code=1)


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
    """
    meta = _load_intent_meta()

    registry_rel = _resolve_from_meta(meta, "mind", "knowledge", "cli_registry")
    schema_rel = _resolve_from_meta(meta, "charter", "schemas", "cli_registry_schema")

    if not registry_rel:
        logger.info(
            "No legacy CLI registry declared in meta.yaml; skipping validation."
        )
        return

    registry_path = (settings.REPO_PATH / registry_rel).resolve()
    schema_path = (settings.REPO_PATH / (schema_rel or "")).resolve()

    if not registry_path.exists():
        logger.info("Legacy CLI registry path not found on disk: %s", registry_rel)
        return

    if not schema_path.exists():
        logger.warning("CLI registry schema not found; skipping validation.")
        return

    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=registry, schema=schema)
        logger.info("✅ Legacy CLI registry is valid: %s", registry_rel)
    except Exception as e:
        logger.error("❌ CLI registry failed validation: %s", e)
        raise typer.Exit(code=1)


# ID: 03edb3b5-ca71-411e-8c90-5249d29a9543
async def check_legacy_tags(ctx: typer.Context) -> None:
    """
    Runs a standalone check for obsolete capability tags using the 'purity' rule set.
    """
    core_context: CoreContext = ctx.obj
    logger.info("🔍 Running standalone legacy tag check...")

    # 1. Initialize AuditorContext
    auditor_context = core_context.auditor_context or AuditorContext(settings.REPO_PATH)
    await auditor_context.load_knowledge_graph()

    # 2. Extract and find the Purity rule
    all_rules = extract_executable_rules(auditor_context.policies)
    target_rule = next(
        (r for r in all_rules if r.rule_id == "purity.no_descriptive_pollution"), None
    )

    if not target_rule:
        logger.warning(
            "Constitutional rule 'purity.no_descriptive_pollution' not found."
        )
        return

    # 3. Execute
    findings = await execute_rule(target_rule, auditor_context)

    if not findings:
        logger.info("✅ Success! No legacy tags found.")
        return

    logger.error("❌ Found %s instance(s) of legacy tags/pollution:", len(findings))
    for finding in findings:
        loc = (
            f"{finding.file_path}:{finding.line_number}"
            if finding.line_number
            else finding.file_path
        )
        logger.error("  [%s] %s: %s", finding.severity.name, loc, finding.message)

    raise typer.Exit(code=1)
