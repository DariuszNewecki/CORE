# scripts/migrations/migrate_cli_registry_v2.py
"""
A one-off migration script to update the core.cli_commands table to the
new verb-noun command structure. THIS SCRIPT IS DESTRUCTIVE.
"""

import asyncio

from services.database.session_manager import get_session
from sqlalchemy import text

# This is the canonical mapping from OLD command name to NEW command name.
# It is the single source of truth for this migration.
RENAME_MAP = {
    "agent.scaffold": "manage.project.onboard",  # Conceptually onboarding
    "bootstrap.issues": "manage.project.bootstrap",
    "build.capability-docs": "manage.project.docs",  # Conceptual mapping
    "byor-init": "manage.project.onboard",
    "capability.new": "fix.ids",  # Conceptually replaced by fix ids
    "chat": "run.agent",  # Conceptually replaced by the agent runner
    "check.ci.audit": "check.audit",
    "check.ci.lint": "check.lint",
    "check.ci.report": "check.report",
    "check.ci.test": "check.tests",
    "check.diagnostics.cli-registry": "check.diagnostics",
    "check.diagnostics.cli-tree": "inspect.command-tree",
    "check.diagnostics.debug-meta": "inspect.meta",  # Simplified
    "check.diagnostics.find-clusters": "inspect.clusters",  # Simplified
    "check.diagnostics.legacy-tags": "check.legacy-tags",
    "check.diagnostics.manifest-hygiene": "check.manifest-hygiene",
    "check.diagnostics.policy-coverage": "check.diagnostics",
    "check.diagnostics.unassigned-symbols": "check.unassigned-symbols",
    "db.export": "manage.database.export",
    "db.migrate": "manage.database.migrate",
    "db.status": "inspect.status",
    "db.sync-domains": "manage.database.sync-domains",
    "fix.assign-ids": "fix.ids",
    "fix.clarity": "fix.clarity",
    "fix.complexity": "fix.complexity",
    "fix.docstrings": "fix.docstrings",
    "fix.format": "fix.code-style",
    "fix.headers": "fix.headers",
    "fix.line-lengths": "fix.line-lengths",
    "fix.orphaned-vectors": "fix.orphaned-vectors",
    "fix.policy-ids": "fix.policy-ids",
    "fix.private-capabilities": "fix.private-capabilities",
    "fix.purge-legacy-tags": "fix.legacy-tags",
    "fix.tags": "fix.tags",
    "guard.drift": "inspect.drift",
    "hub.doctor": "check.cli-registry",
    "hub.list": "inspect.commands",
    "hub.search": "search.commands",
    "hub.whereis": "inspect.command",
    "keygen": "manage.keys.generate",
    "knowledge.audit-ssot": "check.ssot-audit",
    "knowledge.canary": "run.canary",
    "knowledge.export-ssot": "manage.database.export",
    "knowledge.migrate-ssot": "manage.database.migrate-ssot",
    "knowledge.reconcile-from-cli": "manage.database.reconcile",
    "knowledge.search": "search.capabilities",
    "knowledge.sync": "manage.database.sync-knowledge",
    "knowledge.sync-manifest": "manage.database.sync-manifest",
    "knowledge.sync-operational": "manage.database.sync-operational",
    "new": "manage.project.new",
    "proposals.approve": "manage.proposals.approve",
    "proposals.list": "manage.proposals.list",
    "proposals.micro.apply": "manage.proposals.micro-apply",
    "proposals.micro.propose": "manage.proposals.micro-propose",
    "proposals.sign": "manage.proposals.sign",
    "run.develop": "run.agent",
    "run.vectorize": "run.vectorize",
    "system.integrate": "submit.changes",
    "system.process-crates": "run.crates",
    "tools.rewire-imports": "fix.imports",
}


async def main():
    """Connects to the DB and applies the renames."""
    print("🚀 Starting CLI V2 registry migration...")
    updated_count = 0
    async with get_session() as session:
        async with session.begin():
            # Get all current command names from the DB
            result = await session.execute(text("SELECT name FROM core.cli_commands"))
            all_db_commands = [row[0] for row in result]

            # Update existing commands
            for old_name, new_name in RENAME_MAP.items():
                if old_name in all_db_commands:
                    stmt = text(
                        "UPDATE core.cli_commands SET name = :new WHERE name = :old"
                    )
                    result = await session.execute(
                        stmt, {"new": new_name, "old": old_name}
                    )
                    if result.rowcount > 0:
                        print(f"  -> Renamed '{old_name}' to '{new_name}'")
                        updated_count += 1

            # Delete commands that are now conceptually obsolete
            obsolete_commands = [
                cmd for cmd in all_db_commands if cmd not in RENAME_MAP.keys()
            ]
            if obsolete_commands:
                print(f"  -> Deleting {len(obsolete_commands)} obsolete command(s)...")
                delete_stmt = text("DELETE FROM core.cli_commands WHERE name = :name")
                for cmd in obsolete_commands:
                    await session.execute(delete_stmt, {"name": cmd})

    print(f"\n✅ Migration complete. Updated/processed {updated_count} records.")


if __name__ == "__main__":
    asyncio.run(main())
