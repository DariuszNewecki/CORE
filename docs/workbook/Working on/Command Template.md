# EXAMPLE: How to write commands using the new template

"""
This shows how to migrate existing commands to use CommandMeta template.

BEFORE (old way):
    @app.command("symbol-drift")
    async def symbol_drift_command(ctx: typer.Context):
        '''Inspect symbol drift.'''
        ...

AFTER (new way with template):
    @app.command("symbol-drift")
    @command_meta(
        canonical_name="inspect.drift.symbol",
        behavior=CommandBehavior.READ,
        layer=CommandLayer.BODY,
        summary="Inspect symbol drift between code and capabilities"
    )
    async def symbol_drift_command(ctx: typer.Context):
        ...
"""

# ============================================================================
# EXAMPLE 1: Simple READ command
# ============================================================================

import typer
from shared.models.command_meta import CommandMeta, CommandBehavior, CommandLayer, command_meta
from shared.context import CoreContext

app = typer.Typer()

@app.command("status")
@command_meta(
    canonical_name="inspect.status",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Show overall system health and readiness",
    help_text="""
    Displays a comprehensive system status report including:
    - Database connectivity
    - Vector store health
    - Constitutional compliance state
    - Autonomy level

    Example:
        core-admin inspect status
        core-admin inspect status --format json
    """
)
async def status_command(
    ctx: typer.Context,
    format: str = typer.Option("table", "--format", help="Output format")
):
    """Implementation of status command."""
    core_context: CoreContext = ctx.obj
    # ... implementation ...


# ============================================================================
# EXAMPLE 2: VALIDATE command (checks, no mutations)
# ============================================================================

@app.command("lint")
@command_meta(
    canonical_name="check.lint",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.BODY,
    summary="Run static code linting checks",
    constitutional_constraints=["quality.code_standards"]
)
async def lint_command(ctx: typer.Context):
    """Run ruff and other linters."""
    # ... implementation ...


# ============================================================================
# EXAMPLE 3: MUTATE command (changes state, requires --write)
# ============================================================================

@app.command("headers")
@command_meta(
    canonical_name="fix.headers",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.BODY,
    summary="Ensure all files have constitutional headers",
    dangerous=True,  # Requires --write flag
    constitutional_constraints=["quality.file_headers"]
)
async def fix_headers_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Actually apply fixes")
):
    """Fix missing or invalid file headers."""
    if not write:
        # Dry run
        pass
    else:
        # Apply changes
        pass


# ============================================================================
# EXAMPLE 4: AUTONOMOUS command (requires approval)
# ============================================================================

@app.command("propose")
@command_meta(
    canonical_name="autonomy.propose",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Generate an autonomous code modification proposal",
    requires_approval=True,  # Needs human approval before execution
    constitutional_constraints=["autonomy.level_a2", "governance.audit"]
)
async def propose_command(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="What to accomplish")
):
    """Create AI-driven proposal for code changes."""
    # ... Will layer orchestration ...


# ============================================================================
# EXAMPLE 5: Command with ALIASES (backwards compatibility)
# ============================================================================

@app.command("drift")
@command_meta(
    canonical_name="inspect.drift.symbol",
    behavior=CommandBehavior.READ,
    layer=CommandLayer.BODY,
    summary="Inspect symbol drift",
    aliases=["symbol-drift", "drift-symbols"],  # Old names still work
    category="inspection"
)
async def symbol_drift_command(ctx: typer.Context):
    """Check for drift between code symbols and capability registry."""
    # ... implementation ...


# ============================================================================
# EXAMPLE 6: MIND layer command (constitutional governance)
# ============================================================================

@app.command("validate")
@command_meta(
    canonical_name="govern.validate.mind-meta",
    behavior=CommandBehavior.VALIDATE,
    layer=CommandLayer.MIND,
    summary="Validate Mind metadata schemas",
    help_text="Ensures all .intent/ documents conform to constitutional schemas"
)
async def validate_mind_command(ctx: typer.Context):
    """Validate constitutional documents."""
    # ... Mind layer validation ...


# ============================================================================
# HOW fix db-registry EXTRACTS THIS METADATA
# ============================================================================

def example_registry_scanner(app: typer.Typer):
    """
    Pseudocode showing how fix db-registry would scan commands.
    """
    from shared.models.command_meta import get_command_meta, infer_metadata_from_function

    discovered_commands = []

    for cmd_info in app.registered_commands:
        func = cmd_info.callback

        # Try to get explicit metadata first
        meta = get_command_meta(func)

        # Fall back to inference if no decorator
        if meta is None:
            meta = infer_metadata_from_function(
                func=func,
                command_name=cmd_info.name,
                group_prefix=""
            )

        # Now we have complete metadata to sync to DB
        discovered_commands.append({
            "canonical_name": meta.canonical_name,
            "behavior": meta.behavior.value,
            "layer": meta.layer.value,
            "summary": meta.summary,
            "aliases": meta.aliases,
            "module": meta.module or func.__module__,
            "entrypoint": meta.entrypoint or func.__name__,
            "dangerous": meta.dangerous,
            "requires_approval": meta.requires_approval,
            "constitutional_constraints": meta.constitutional_constraints,
        })

    return discovered_commands


# ============================================================================
# MIGRATION STRATEGY
# ============================================================================

"""
Phase 1: Add @command_meta to new commands (optional for existing)
Phase 2: Update fix db-registry to extract metadata
Phase 3: Gradually migrate existing commands
Phase 4: Make @command_meta mandatory (constitutional requirement)

During migration, commands without @command_meta still work (inference fallback).
"""
