# src/will/interpreters/cli_args_interpreter.py

"""
CLIArgsInterpreter — explicit CLI args → TaskStructure.

INTERPRET-phase implementation for explicit commands like
`core-admin fix clarity src/models/user.py --write`. CLI args already
carry structure; this interpreter normalises (command, subcommand,
targets, flags) into the canonical TaskStructure.

This module owns the mapping from top-level CLI commands to TaskType.
When a new top-level command needs interpretation (or a new flag needs
to be lifted into constraints), this is the module that changes.

The contract (RequestInterpreter base, TaskType, TaskStructure) lives in
request_interpreter.py.

LAYER: will/interpreters — sibling of natural_language_interpreter.py.
No DB access, no file writes, no LLM calls.
"""

from __future__ import annotations

from shared.component_primitive import ComponentResult
from will.interpreters.request_interpreter import (
    RequestInterpreter,
    TaskStructure,
    TaskType,
)


# ID: 94271d67-67b4-4b39-8020-b944cd99f657
class CLIArgsInterpreter(RequestInterpreter):
    """
    Interprets CLI arguments into TaskStructure.

    This is for explicit commands like:
        core-admin fix clarity src/models/user.py --write

    Already has structure, just needs normalization.
    """

    # ID: 77647948-e7ef-4b02-a014-1bfde2b25f91
    async def execute(
        self,
        command: str,
        subcommand: str | None = None,
        targets: list[str] | None = None,
        **flags,
    ) -> ComponentResult:
        """
        Parse CLI args → TaskStructure.

        Args:
            command: Main command (fix, check, generate, etc)
            subcommand: Optional subcommand (clarity, complexity, etc)
            targets: List of file paths
            **flags: CLI flags (write, verbose, etc)

        Returns:
            ComponentResult with TaskStructure
        """
        import time

        start = time.time()

        # Map command → TaskType
        task_type_map = {
            "fix": TaskType.FIX,
            "check": TaskType.AUDIT,
            "generate": TaskType.GENERATE,
            "coverage": TaskType.TEST,
            "develop": TaskType.DEVELOP,
            "sync": TaskType.SYNC,
        }

        task_type = task_type_map.get(command, TaskType.UNKNOWN)

        # Build intent from command structure
        intent_parts = [command]
        if subcommand:
            intent_parts.append(subcommand)
        if targets:
            intent_parts.extend(targets)
        intent = " ".join(intent_parts)

        task = TaskStructure(
            task_type=task_type,
            intent=intent,
            targets=targets or [],
            constraints=flags,
            context={
                "source": "cli_args",
                "command": command,
                "subcommand": subcommand,
            },
            confidence=1.0 if task_type != TaskType.UNKNOWN else 0.3,
        )

        result = self._create_result(
            task,
            metadata={"command": command, "subcommand": subcommand, "flags": flags},
        )
        result.duration_sec = time.time() - start

        return result
