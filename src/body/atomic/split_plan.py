# src/body/atomic/split_plan.py

"""
Deterministic split plan data models.

These dataclasses describe a modularization plan produced by LLM boundary
decisions.  They carry no execution logic — the caller (ModularitySplitter)
reads them and the Execution phase writes files.

Constitutional note:
  Body layer — no settings access, no file I/O, no LLM calls.
"""

from __future__ import annotations

import json
import keyword
from dataclasses import dataclass, field
from typing import Any


# ID: d7e3a1c4-6f28-4b9e-a1d3-5c8e0f2b7a96
class SplitPlanError(Exception):
    """Raised when a split plan is malformed or violates constraints."""


@dataclass(frozen=True)
# ID: 6a699885-73dd-4224-91de-526674975950
class ModuleSpec:
    """One target module inside a split plan."""

    module_name: str
    symbols: list[str]
    rationale: str


@dataclass
# ID: 4b9defe6-3c2c-4840-ae20-c460f77c550f
class SplitPlan:
    """Complete plan for splitting a single source file into a package."""

    source_file: str
    new_package_name: str
    modules: list[ModuleSpec] = field(default_factory=list)

    # ID: 8e1d4a7b-3c6f-4928-b5d0-2a9e8c1f7b3d
    def validate(self) -> None:
        """Validate plan constraints.  Raises SplitPlanError on failure."""
        if len(self.modules) < 2:
            raise SplitPlanError(
                f"Plan must contain at least 2 modules, got {len(self.modules)}"
            )

        seen: set[str] = set()
        for mod in self.modules:
            if not mod.symbols:
                raise SplitPlanError(
                    f"Module '{mod.module_name}' has an empty symbol list"
                )

            if not mod.module_name.isidentifier() or keyword.iskeyword(mod.module_name):
                raise SplitPlanError(
                    f"'{mod.module_name}' is not a valid Python identifier"
                )

            for sym in mod.symbols:
                if sym in seen:
                    raise SplitPlanError(
                        f"Symbol '{sym}' appears in more than one module"
                    )
                seen.add(sym)

    @classmethod
    # ID: 34df5f9e-0309-4fc8-9f46-b2b9d568d307
    def from_llm_json(cls, raw: str) -> SplitPlan:
        """Parse LLM JSON response into a validated SplitPlan.

        Raises SplitPlanError if JSON is malformed or validation fails.
        """
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
        try:
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise SplitPlanError(f"Malformed JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise SplitPlanError(f"Expected a JSON object, got {type(data).__name__}")

        modules: list[ModuleSpec] = []
        for entry in data.get("modules", []):
            modules.append(
                ModuleSpec(
                    module_name=str(entry.get("module_name", "")),
                    symbols=list(entry.get("symbols", [])),
                    rationale=str(entry.get("rationale", "")),
                )
            )

        plan = cls(
            source_file=str(data.get("source_file", "")),
            new_package_name=str(data.get("new_package_name", "")),
            modules=modules,
        )
        plan.validate()
        return plan
