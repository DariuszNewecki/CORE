# src/body/cli/logic/diagnostics_registry.py

"""
Logic for auditing domain manifests and legacy artifacts.
Refactored to use the dynamic constitutional rule engine and PathResolver.
"""

from __future__ import annotations

import json

import jsonschema
import typer
import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import AuditSeverity
from shared.path_resolver import PathResolver


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
    auditor_context = core_context.auditor_context or AuditorContext(
        core_context.git_service.repo_path
    )
    await auditor_context.load_knowledge_graph()

    # 2. Extract rules using the mandatory enforcement_loader
    # CONSTITUTIONAL FIX: Passed enforcement_loader as the second argument
    all_rules = extract_executable_rules(
        auditor_context.policies, auditor_context.enforcement_loader
    )

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


# ID: 67db4c4d-4483-4d71-9044-a1464ae3a4b2
def cli_registry(ctx: typer.Context) -> None:
    """
    Validates the *legacy* CLI registry YAML (if still present) against its schema.
    """
    # Use PathResolver to find standard locations
    core_context: CoreContext = ctx.obj
    path_resolver = PathResolver.from_repo(
        repo_root=core_context.git_service.repo_path,
        intent_root=core_context.git_service.repo_path / ".intent",
    )

    registry_path = path_resolver.knowledge_dir / "cli_registry.yaml"

    try:
        # Resolve schema via the unified policy/standard search
        schema_path = path_resolver.policy("cli_registry_schema")
    except FileNotFoundError:
        logger.info(
            "CLI registry schema not found via PathResolver; skipping validation."
        )
        return

    if not registry_path.exists():
        logger.info("Legacy CLI registry not found at %s; skipping.", registry_path)
        return

    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=registry, schema=schema)
        logger.info("✅ Legacy CLI registry is valid: %s", registry_path.name)
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
    auditor_context = core_context.auditor_context or AuditorContext(
        core_context.git_service.repo_path
    )
    await auditor_context.load_knowledge_graph()

    # 2. Extract rules using the mandatory enforcement_loader
    # CONSTITUTIONAL FIX: Passed enforcement_loader
    all_rules = extract_executable_rules(
        auditor_context.policies, auditor_context.enforcement_loader
    )

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
