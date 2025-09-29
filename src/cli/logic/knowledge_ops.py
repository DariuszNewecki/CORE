# src/cli/commands/knowledge_ops.py
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List

import typer
import yaml
from rich.console import Console
from rich.table import Table
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from core.cognitive_service import CognitiveService
from features.introspection.generate_correction_map import generate_maps  # noqa: F401
from features.introspection.semantic_clusterer import run_clustering  # noqa: F401
from services.database.models import CliCommand, CognitiveRole, LlmResource
from services.database.session_manager import get_session
from shared.config import settings
from shared.legacy_models import (
    LegacyCliRegistry,
    LegacyCognitiveRoles,
    LegacyResourceManifest,
)

# Optional: governance audit (adaptive to DB schema, already added earlier)
try:
    from features.governance.checks.knowledge_source_check import (  # type: ignore
        KnowledgeSourceCheck,
    )
except Exception:  # pragma: no cover
    KnowledgeSourceCheck = None

console = Console()

# ----- Constants -----
MIND_KNOWLEDGE_DIR = settings.MIND / "knowledge"
Y_CLI = MIND_KNOWLEDGE_DIR / "cli_registry.yaml"
Y_RES = MIND_KNOWLEDGE_DIR / "resource_manifest.yaml"
Y_ROLES = MIND_KNOWLEDGE_DIR / "cognitive_roles.yaml"


def _safe_yaml_load(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# =====================================================================
# Helpers: AsyncEngine, column introspection, YAML write, run cmd
# =====================================================================


async def _acquire_async_engine() -> AsyncEngine:
    """
    Extract an AsyncEngine from the session manager, trying several safe paths.
    """
    async with get_session() as session:
        # 1) Preferred: real AsyncConnection -> engine
        try:
            conn = await session.connection()
            if isinstance(conn, AsyncConnection):
                return conn.engine  # type: ignore[return-value]
        except Exception:
            pass

        # 2) Fallbacks
        try:
            bind = session.get_bind()
        except Exception:
            bind = None

        if isinstance(bind, AsyncEngine):
            return bind
        if isinstance(bind, AsyncConnection):
            return bind.engine  # type: ignore[return-value]
        engine = getattr(bind, "engine", None)
        if isinstance(engine, AsyncEngine):
            return engine

        maybe_engine = getattr(session, "bind", None)
        if isinstance(maybe_engine, AsyncEngine):
            return maybe_engine
        if hasattr(session, "sync_session"):
            sync_bind = getattr(session.sync_session, "bind", None)  # type: ignore[attr-defined]
            if hasattr(sync_bind, "engine"):
                eng = getattr(sync_bind, "engine")
                if isinstance(eng, AsyncEngine):
                    return eng

    raise RuntimeError("Could not acquire AsyncEngine from session manager.")


async def _list_columns(session: AsyncSession, schema: str, table: str) -> List[str]:
    sql = text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema AND table_name = :table
        ORDER BY ordinal_position
        """
    )
    rows = (await session.execute(sql, {"schema": schema, "table": table})).mappings()
    return [r["column_name"] for r in rows]


async def _fetch_table(
    session: AsyncSession, schema: str, table: str, preferred_order: List[str]
) -> tuple[List[Dict[str, Any]], List[str]]:
    cols = await _list_columns(session, schema, table)
    if not cols:
        return [], []

    select_cols = ", ".join([f'"{c}"' for c in cols])
    sql = text(f'SELECT {select_cols} FROM "{schema}"."{table}"')
    rows = (await session.execute(sql)).mappings().all()
    data = [dict(r) for r in rows]

    ordered_cols = [c for c in preferred_order if c in cols] + [
        c for c in cols if c not in preferred_order
    ]
    data = [{k: rec.get(k) for k in ordered_cols} for rec in data]
    return data, ordered_cols


def _dump_yaml_list(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    items_sorted = sorted(items, key=lambda d: str(d.get("name", "")))
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(items_sorted, f, sort_keys=True, allow_unicode=True)


async def _run_cmd_async(cmd: List[str]) -> int:
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    proc = await asyncio.create_subprocess_exec(*cmd)
    return await proc.wait()


# =====================================================================
# Commands (same behavior as before)
# =====================================================================


# ID: ce6ffa34-2440-4188-bc95-0f6703651b9a
def search_knowledge_command(query: str, limit: int = 5) -> None:
    """Synchronous wrapper around async search."""

    async def _run() -> None:
        console.print(
            f"🧠 Searching for capabilities related to: '[cyan]{query}[/cyan]'..."
        )
        try:
            cognitive_service = CognitiveService(settings.REPO_PATH)
            results = await cognitive_service.search_capabilities(query, limit=limit)
            if not results:
                console.print("[yellow]No relevant capabilities found.[/yellow]")
                return

            table = Table(title="Top Matching Capabilities")
            table.add_column("Score", style="magenta", justify="right")
            table.add_column("Capability Key", style="cyan")
            table.add_column("Description", style="green")
            for hit in results:
                payload = hit.get("payload", {}) or {}
                key = payload.get("key", "N/A")
                description = (
                    payload.get("description") or "No description provided."
                ).strip()
                score = f"{hit.get('score', 0):.4f}"
                table.add_row(score, key, description)
            console.print(table)
        except Exception as e:
            console.print(f"[bold red]❌ Search failed: {e}[/bold red]")
            raise typer.Exit(code=1)

    asyncio.run(_run())


# ID: fb327da3-89a2-4b7f-8bff-ac8df6e054eb
def migrate_ssot_command(force: bool = False) -> None:
    """One-time migration of legacy YAML → DB."""

    async def _run() -> None:
        console.print(
            "[bold yellow]⚠️ WARNING: One-time migration operation.[/bold yellow]"
        )
        console.print(
            "   Reads legacy YAML files and populates the database, replacing existing data."
        )
        if not force and not typer.confirm("Are you sure you want to proceed?"):
            raise typer.Abort()

        async with get_session() as session:
            # CLI registry
            if Y_CLI.exists():
                console.print(f"Migrating [cyan]{Y_CLI.name}[/cyan]...")
                data = _safe_yaml_load(Y_CLI) or {}
                registry_model = LegacyCliRegistry.model_validate(data)
                commands_data = [
                    c.model_dump() for c in (registry_model.commands or [])
                ]
                if commands_data:
                    await session.execute(CliCommand.__table__.delete())
                    await session.execute(insert(CliCommand), commands_data)
                console.print(f"  -> Migrated {len(commands_data)} CLI commands.")
            else:
                console.print("[yellow]Skipping CLI registry: file not found.[/yellow]")

            # LLM resources
            if Y_RES.exists():
                console.print(f"Migrating [cyan]{Y_RES.name}[/cyan]...")
                data = _safe_yaml_load(Y_RES) or {}
                manifest_model = LegacyResourceManifest.model_validate(data)
                resources_data = [
                    r.model_dump() for r in (manifest_model.llm_resources or [])
                ]
                if resources_data:
                    await session.execute(LlmResource.__table__.delete())
                    await session.execute(insert(LlmResource), resources_data)
                console.print(f"  -> Migrated {len(resources_data)} LLM resources.")
            else:
                console.print(
                    "[yellow]Skipping LLM resources: file not found.[/yellow]"
                )

            # Cognitive roles
            if Y_ROLES.exists():
                console.print(f"Migrating [cyan]{Y_ROLES.name}[/cyan]...")
                data = _safe_yaml_load(Y_ROLES) or {}
                roles_model = LegacyCognitiveRoles.model_validate(data)
                roles_data = [
                    r.model_dump() for r in (roles_model.cognitive_roles or [])
                ]
                if roles_data:
                    await session.execute(CognitiveRole.__table__.delete())
                    await session.execute(insert(CognitiveRole), roles_data)
                console.print(f"  -> Migrated {len(roles_data)} cognitive roles.")
            else:
                console.print(
                    "[yellow]Skipping cognitive roles: file not found.[/yellow]"
                )

            await session.commit()

        console.print(
            "\n[bold green]✅ Knowledge migration complete. The database is now the SSOT.[/bold green]"
        )
        console.print(
            "[bold yellow]You may now remove the legacy YAML files from .intent/mind/knowledge/.[/bold yellow]"
        )

    asyncio.run(_run())


# ID: 35b7c323-e362-40b7-a49a-79e369d1bae0
def audit_ssot_command() -> None:
    """Run governance audit comparing DB ↔ YAML (skips missing YAML unless strict mode)."""
    if KnowledgeSourceCheck is None:
        console.print(
            "[bold yellow]KnowledgeSourceCheck not available; cannot audit SSOT.[/bold yellow]"
        )
        raise typer.Exit(code=2)

    async def _run() -> None:
        repo_root = Path(settings.REPO_PATH)
        try:
            engine = await _acquire_async_engine()
        except Exception as e:
            console.print(f"[bold red]❌ Could not acquire AsyncEngine: {e}[/bold red]")
            raise typer.Exit(code=1)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        strict = os.getenv("CORE_REQUIRE_YAML_EXPORTS") == "1"

        check = KnowledgeSourceCheck(
            repo_root=repo_root,
            engine=engine,
            session_factory=session_factory,
            reports_dir=repo_root / "reports" / "knowledge_ssot",
            require_yaml_exports=strict,
        )
        result = await check.run()

        if result.passed:
            console.print(
                "[bold green]✅ SSOT audit passed: no drift detected.[/bold green]"
            )
            raise typer.Exit(code=0)

        console.print(
            "[bold red]❌ SSOT audit failed: drift detected. See report for details.[/bold red]"
        )
        sections = result.details.get("sections", {})
        for name, payload in sections.items():
            status = payload.get("status")
            if status == "skipped":
                console.print(f"  • {name}: skipped (yaml missing)")
                continue
            diff = payload.get("diff", {}) or {}
            miss_db = len(diff.get("missing_in_db", []) or [])
            miss_yaml = len(diff.get("missing_in_yaml", []) or [])
            mism = len(diff.get("mismatched", []) or [])
            console.print(
                f"  • {name}: missing_in_db={miss_db}, missing_in_yaml={miss_yaml}, mismatched={mism}"
            )
        raise typer.Exit(code=1)

    asyncio.run(_run())


# ID: 7e167d8e-88e7-47b6-8685-1bdf6ae06e1b
def export_ssot_command() -> None:
    """Export DB → .intent/mind/knowledge/*.yaml (read-only snapshots)."""

    async def _run() -> None:
        try:
            engine = await _acquire_async_engine()
        except Exception as e:
            console.print(f"[bold red]❌ Could not acquire AsyncEngine: {e}[/bold red]")
            raise typer.Exit(code=1)

        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            cli_rows, _ = await _fetch_table(
                session,
                "core",
                "cli_commands",
                ["name", "module", "entrypoint", "enabled"],
            )
            llm_rows, _ = await _fetch_table(
                session,
                "core",
                "llm_resources",
                ["name", "provider", "model", "enabled"],
            )
            roles_rows, _ = await _fetch_table(
                session, "core", "cognitive_roles", ["name", "description", "enabled"]
            )

        _dump_yaml_list(Y_CLI, cli_rows)
        _dump_yaml_list(Y_RES, llm_rows)
        _dump_yaml_list(Y_ROLES, roles_rows)

        # ID: 8d7f623d-0218-4042-a340-25958a1dfd75
        def rel(path: Path) -> str:
            """Return repo-relative path for pretty printing; fall back to plain path."""
            try:
                return str(
                    path.resolve().relative_to(Path(settings.REPO_PATH).resolve())
                )
            except Exception:
                try:
                    return os.path.relpath(str(path), start=str(settings.REPO_PATH))
                except Exception:
                    return str(path)

        console.print("[bold green]✅ Export complete.[/bold green]")
        console.print(f"  • {rel(Y_CLI)}")
        console.print(f"  • {rel(Y_RES)}")
        console.print(f"  • {rel(Y_ROLES)}")

    asyncio.run(_run())


# ID: 80939ec5-7388-4b90-a4d2-796d8a90e60c
def canary_command(skip_lint: bool = False, skip_tests: bool = False) -> None:
    """Run SSOT audit → ruff → pytest; fail fast on any issue."""

    async def _run() -> None:
        console.print("[bold]⛳  Canary: SSOT audit[/bold]")
        code = await _run_cmd_async(
            ["python3", "-m", "poetry", "run", "core-admin", "knowledge", "audit-ssot"]
        )
        if code != 0:
            raise typer.Exit(code=code)

        if not skip_lint:
            console.print("[bold]⛳  Canary: Ruff linter[/bold]")
            code = await _run_cmd_async(
                ["python3", "-m", "poetry", "run", "ruff", "check"]
            )
            if code != 0:
                raise typer.Exit(code=code)

        if not skip_tests:
            console.print("[bold]⛳  Canary: Pytest[/bold]")
            code = await _run_cmd_async(
                ["python3", "-m", "poetry", "run", "pytest", "-q"]
            )
            if code != 0:
                raise typer.Exit(code=code)

        console.print("[bold green]✅ Canary passed[/bold green]")

    asyncio.run(_run())
