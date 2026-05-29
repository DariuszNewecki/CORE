# src/mind/logic/engines/cli_gate/__init__.py

"""CLI Gate Engine — context-level audit of the Typer command registry.

Architecture mirrors workflow_gate:
- engine.py: orchestrator that lazily imports the Typer app and dispatches
  to one of eight check classes, sharing the walked command registry
  across them.
- base_check.py: ``CliCheck`` ABC.
- checks/: one file per check_type.

Adding a new check_type:
1. Add check_types/my_check.py inheriting from CliCheck.
2. Re-export it via checks/__init__.py.
3. Instantiate it in engine.py's __init__ list.
4. Wire a mapping under .intent/enforcement/mappings/ with
   ``engine: cli_gate`` and ``params.check_type: my_check``.
"""

from __future__ import annotations

from mind.logic.engines.cli_gate.engine import CliGateEngine


__all__ = ["CliGateEngine"]
