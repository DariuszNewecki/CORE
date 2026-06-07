# src/shared/infrastructure/context/shadow_diff.py

"""
ShadowDiff — structural diff between a disk Knowledge Graph and a shadow graph.

Surfaces the consequences of proposed (uncommitted) changes at symbol granularity:
which classes/functions were added, removed, had their signatures changed, and
which symbols still call names the shadow graph no longer defines.

The audit-over-shadow signal (see ShadowAuditDiff) is the load-bearing pain
receptor for V2.3-REBIRTH Limbs. ShadowDiff is the cheap, deterministic,
LLM-free structural belt-and-braces alongside it.

Constitutional alignment:
- Pillar II (UNIX Neuron): pure function over two graph dicts. No I/O, no DB.
- Pillar III (Functional Governance): Brain-as-Governor consumes these facts to
  decide whether to authorize a Limb's proposed change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ID: cf4bff12-f57d-4da1-8e46-bcd5ca2fcb79
@dataclass(frozen=True)
class SymbolRef:
    """Lightweight reference to a symbol in either graph."""

    symbol_path: str  # "<file>::<name>"
    name: str
    file_path: str
    kind: str  # "FunctionDef" / "AsyncFunctionDef" / "ClassDef"


# ID: 97a6552d-16b9-40d9-88a5-47105c8fb06b
@dataclass(frozen=True)
class SignatureDelta:
    """A symbol whose parameter list changed between disk and shadow."""

    symbol_path: str
    name: str
    file_path: str
    disk_parameters: tuple[Any, ...]
    shadow_parameters: tuple[Any, ...]


# ID: 2a2099fa-79b5-43bd-a914-902f89458e7c
@dataclass(frozen=True)
class OrphanedCaller:
    """A symbol in the shadow graph that calls a name the shadow no longer defines.

    Caller and orphaned-call name are both repo-internal — calls into stdlib or
    third-party packages are not orphans even if absent from the symbol index.
    """

    caller_symbol_path: str
    caller_name: str
    caller_file_path: str
    orphaned_call: str  # the name being called that no longer exists


# ID: 226bf131-592a-4785-948e-5a8d55a624ab
class ShadowDiff:
    """Compute the structural diff between a disk graph and a shadow graph.

    Both inputs are dicts produced by KnowledgeGraphBuilder.build() — see
    src/shared/infrastructure/knowledge_graph_service.py for the schema.

    The expected shape:
        {"metadata": {...}, "symbols": {"<file>::<name>": {symbol_data}}}

    Where each symbol_data has at least: name, type, file_path, parameters,
    calls (a list of names called by this symbol).
    """

    # ID: 26b0d1a2-325c-4313-980f-739cc5130568
    def __init__(self, disk_graph: dict[str, Any], shadow_graph: dict[str, Any]):
        self._disk_symbols: dict[str, dict[str, Any]] = disk_graph.get("symbols", {})
        self._shadow_symbols: dict[str, dict[str, Any]] = shadow_graph.get(
            "symbols", {}
        )
        self._disk_names: frozenset[str] = frozenset(
            data.get("name", "")
            for data in self._disk_symbols.values()
            if data.get("name")
        )
        self._shadow_names: frozenset[str] = frozenset(
            data.get("name", "")
            for data in self._shadow_symbols.values()
            if data.get("name")
        )

    # ID: 1689146f-ea4d-42d6-978a-2ddfc1479987
    def added_symbols(self) -> list[SymbolRef]:
        """Symbols present in shadow but not in disk."""
        new_keys = self._shadow_symbols.keys() - self._disk_symbols.keys()
        return sorted(
            (self._to_ref(key, self._shadow_symbols[key]) for key in new_keys),
            key=lambda r: r.symbol_path,
        )

    # ID: 60f2d3ec-acef-4710-9766-b4d5f4603d44
    def removed_symbols(self) -> list[SymbolRef]:
        """Symbols present in disk but not in shadow."""
        gone_keys = self._disk_symbols.keys() - self._shadow_symbols.keys()
        return sorted(
            (self._to_ref(key, self._disk_symbols[key]) for key in gone_keys),
            key=lambda r: r.symbol_path,
        )

    # ID: 556e2a99-a89c-48dc-857a-ca407324fa27
    def changed_signatures(self) -> list[SignatureDelta]:
        """Symbols present in both graphs whose parameter lists differ.

        Parameters are compared as the tuple form of whatever the graph
        builder serialized — typically a list of dicts. List inequality is
        sufficient to detect added/removed/renamed/reordered parameters.
        """
        deltas: list[SignatureDelta] = []
        for key in self._disk_symbols.keys() & self._shadow_symbols.keys():
            disk_params = tuple(self._disk_symbols[key].get("parameters") or ())
            shadow_params = tuple(self._shadow_symbols[key].get("parameters") or ())
            if disk_params != shadow_params:
                data = self._shadow_symbols[key]
                deltas.append(
                    SignatureDelta(
                        symbol_path=key,
                        name=data.get("name", ""),
                        file_path=data.get("file_path", ""),
                        disk_parameters=disk_params,
                        shadow_parameters=shadow_params,
                    )
                )
        return sorted(deltas, key=lambda d: d.symbol_path)

    # ID: 24c8cd51-1b30-40a0-a2d8-e76562ed79d8
    def orphaned_callers(self) -> list[OrphanedCaller]:
        """Shadow-graph symbols that call repo-internal names the shadow doesn't define.

        A name is considered repo-internal — and thus capable of being orphaned —
        iff it was defined in the disk graph. Calls to symbols that never existed
        in either graph (stdlib, third-party, builtins) are filtered out: they
        were never the limb's promise to keep alive.
        """
        orphans: list[OrphanedCaller] = []
        for key, data in self._shadow_symbols.items():
            calls = data.get("calls") or []
            for call_name in calls:
                if not call_name:
                    continue
                # Only repo-internal symbols qualify as orphan-candidates.
                if call_name not in self._disk_names:
                    continue
                # Still defined in shadow? Not an orphan.
                if call_name in self._shadow_names:
                    continue
                orphans.append(
                    OrphanedCaller(
                        caller_symbol_path=key,
                        caller_name=data.get("name", ""),
                        caller_file_path=data.get("file_path", ""),
                        orphaned_call=call_name,
                    )
                )
        return sorted(orphans, key=lambda o: (o.caller_symbol_path, o.orphaned_call))

    # ID: f3f5509e-c6ed-4c9b-8b53-8c907e1a4fb4
    def is_empty(self) -> bool:
        """True iff no structural change of any kind was detected."""
        return (
            not self.added_symbols()
            and not self.removed_symbols()
            and not self.changed_signatures()
            and not self.orphaned_callers()
        )

    @staticmethod
    def _to_ref(key: str, data: dict[str, Any]) -> SymbolRef:
        return SymbolRef(
            symbol_path=key,
            name=data.get("name", ""),
            file_path=data.get("file_path", ""),
            kind=data.get("type", ""),
        )


__all__ = ["OrphanedCaller", "ShadowDiff", "SignatureDelta", "SymbolRef"]
