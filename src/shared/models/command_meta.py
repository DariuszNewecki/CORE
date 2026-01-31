# src/shared/models/command_meta.py

"""
Command Metadata Template - Constitutional Contract for CLI Commands

Every command in core-admin MUST provide this metadata.
This ensures:
- Consistent command structure
- Automatic registry discovery
- Proper routing
- Constitutional compliance

Usage:
    @app.command("drift")
    @command_meta(
        canonical_name="inspect.drift.symbol",
        behavior=CommandBehavior.READ,
        layer=CommandLayer.BODY,
        summary="Inspect symbol drift between code and capabilities"
    )
    async def symbol_drift_command(ctx: typer.Context):
        ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


# ID: 827dbbaf-da04-4f07-8aee-83c68f30bc33
class CommandBehavior(str, Enum):
    """What does this command DO to the system?"""

    READ = "read"  # Pure inspection, no mutations (inspect, list, show)
    VALIDATE = "validate"  # Checks that can fail, no mutations (check, audit, test)
    MUTATE = "mutate"  # Changes system state (fix, sync, generate, update)
    TRANSFORM = "transform"  # Data migrations, imports/exports


# ID: 943436b9-23c4-4716-929b-107b0bb69ab2
class CommandLayer(str, Enum):
    """Which architectural layer does this belong to?"""

    MIND = "mind"  # Constitutional/governance operations (.intent/ interaction)
    BODY = "body"  # Pure execution, infrastructure, tools
    WILL = "will"  # Autonomous/cognitive operations (requires AI decision-making)


@dataclass
# ID: a28a8e9e-aacb-4cb4-940c-87d096f01dca
class CommandMeta:
    """
    Template/Contract for all CLI commands.

    REQUIRED fields (command won't work without these):
        - canonical_name: Hierarchical name like "inspect.drift.symbol"
        - behavior: What category of operation (read/validate/mutate/transform)
        - layer: Which architectural layer (mind/body/will)
        - summary: One-line description for --help

    OPTIONAL fields:
        - aliases: Alternative names for backwards compatibility
        - help_text: Extended help with examples
        - dangerous: Requires --write or confirmation
        - requires_approval: Needs autonomy approval before execution
        - constitutional_constraints: Policy rules that must be satisfied
    """

    # === REQUIRED FIELDS ===
    canonical_name: str
    """Hierarchical command name: 'group.subgroup.action' (e.g., 'inspect.drift.symbol')"""

    behavior: CommandBehavior
    """What does this command do? (read/validate/mutate/transform)"""

    layer: CommandLayer
    """Which architectural layer? (mind/body/will)"""

    summary: str
    """One-line description shown in --help"""

    # === OPTIONAL FIELDS ===
    aliases: list[str] = field(default_factory=list)
    """Alternative command names for backwards compatibility"""

    help_text: str | None = None
    """Extended help text with examples and usage notes"""

    category: str | None = None
    """Logical grouping: 'inspection', 'governance', 'maintenance'"""

    dangerous: bool = False
    """Whether command mutates state (requires --write flag or confirmation)"""

    requires_approval: bool = False
    """Whether execution needs Will layer approval (autonomous operations)"""

    constitutional_constraints: list[str] = field(default_factory=list)
    """Required policy rules: ['audit.read', 'governance.inspect']"""

    # Extracted automatically by registry scanner
    module: str | None = None
    """Python module path (auto-filled by scanner): 'body.cli.commands.inspect'"""

    entrypoint: str | None = None
    """Function name (auto-filled by scanner): 'symbol_drift_command'"""

    def __post_init__(self):
        """Validate required fields."""
        if not self.canonical_name:
            raise ValueError("canonical_name is required")
        if not self.summary:
            raise ValueError("summary is required")

        # Auto-generate category from canonical_name if not provided
        if not self.category and "." in self.canonical_name:
            parts = self.canonical_name.split(".")
            self.category = parts[0] if len(parts) > 1 else "general"


# === DECORATOR FOR ATTACHING METADATA TO COMMANDS ===


# ID: e5878f2a-5950-4cc3-afa0-1ae99ad528c9
def command_meta(**kwargs) -> Callable:
    """
    Decorator to attach metadata to command functions.

    Usage:
        @app.command("symbol-drift")
        @command_meta(
            canonical_name="inspect.drift.symbol",
            behavior=CommandBehavior.READ,
            layer=CommandLayer.BODY,
            summary="Inspect symbol drift"
        )
        async def symbol_drift_command(ctx: typer.Context):
            ...

    The metadata is stored on the function as __command_meta__ attribute,
    which fix db-registry can extract during scanning.
    """
    meta = CommandMeta(**kwargs)

    # ID: 258dc4d7-d473-45ea-b32b-31726a0b01df
    def decorator(func: Callable) -> Callable:
        func.__command_meta__ = meta
        return func

    return decorator


# === HELPER FUNCTIONS ===


# ID: e7b7073d-b36b-4fc1-b2fc-984cd0bdf35f
def get_command_meta(func: Callable) -> CommandMeta | None:
    """Extract CommandMeta from a decorated function, or None if not present."""
    return getattr(func, "__command_meta__", None)


# ID: 86a24e3f-5328-441f-b7ab-c3e1abb3be75
def infer_metadata_from_function(
    func: Callable, command_name: str, group_prefix: str = ""
) -> CommandMeta:
    """
    Fallback: infer metadata from function when @command_meta is missing.

    Used by registry scanner for commands that don't have explicit metadata yet.
    Tries to guess behavior/layer from function name and docstring.
    """
    docstring = func.__doc__ or ""
    first_line = docstring.strip().split("\n")[0] if docstring else "No description"

    full_name = f"{group_prefix}{command_name}" if group_prefix else command_name

    # Guess behavior from function name
    func_name_lower = func.__name__.lower()
    if any(
        word in func_name_lower for word in ["list", "show", "inspect", "get", "search"]
    ):
        behavior = CommandBehavior.READ
    elif any(
        word in func_name_lower
        for word in ["check", "validate", "verify", "test", "audit"]
    ):
        behavior = CommandBehavior.VALIDATE
    elif any(
        word in func_name_lower
        for word in ["fix", "sync", "update", "generate", "create"]
    ):
        behavior = CommandBehavior.MUTATE
    elif any(
        word in func_name_lower for word in ["migrate", "export", "import", "transform"]
    ):
        behavior = CommandBehavior.TRANSFORM
    else:
        behavior = CommandBehavior.READ  # default safe assumption

    # Guess layer from module path
    module = func.__module__
    if "will" in module or "autonomous" in module or "cognitive" in module:
        layer = CommandLayer.WILL
    elif "mind" in module or "governance" in module or "intent" in module:
        layer = CommandLayer.MIND
    else:
        layer = CommandLayer.BODY

    return CommandMeta(
        canonical_name=full_name,
        behavior=behavior,
        layer=layer,
        summary=first_line,
        module=module,
        entrypoint=func.__name__,
    )
