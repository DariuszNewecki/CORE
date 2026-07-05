# src/mind/coherence/checks/intent_binding.py
"""INTENT_BINDING — .intent/ artifact names a Python symbol that does not exist in src/.

Scans:
  - .intent/phases/*.yaml        for  implementation: <dotted.Python.Path>
  - .intent/enforcement/mappings/**/*.yaml  for  enforced_by: "<dotted.Python.Path>"

For each declared path, resolves the module to src/<module>.py (or
src/<module>/__init__.py) and verifies the symbol name appears in
the file. No imports executed — pure filesystem + text search.

No LLM. No vectors. No runtime imports.

Addresses CCC scope gap F-06 (.intent/→src/ reverse-reference validity).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .base import CoherenceCandidate


# ID: 6ffd7dad-cbb0-47e0-9edd-eb44dfa69646
class IntentBindingCheck:
    """Emit INTENT_BINDING for .intent/ Python path declarations that do not resolve."""

    relation = "INTENT_BINDING"

    # ID: a62971e4-9d3d-41ae-aeef-0bceeac2fe48
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: a372df1f-11bf-4d99-8cc3-a621c35abb6e
    async def run(self) -> list[CoherenceCandidate]:
        candidates: list[CoherenceCandidate] = []
        for doc_path, field, value in self._collect_bindings():
            error = self._check_binding(value)
            if error is None:
                continue
            rel_doc = str(doc_path.relative_to(self._repo_root))
            candidates.append(
                CoherenceCandidate(
                    relation=self.relation,
                    documents=[rel_doc],
                    claim=(f"`{rel_doc}` declares `{field}: {value}` but {error}."),
                    rationale=(
                        f"Every `{field}:` declaration in `.intent/` must resolve "
                        "to a real Python symbol in `src/`. When a class or function "
                        "is renamed or moved, the `.intent/` binding must be updated "
                        "to match. A stale binding silently disconnects the declared "
                        "enforcement mechanism."
                    ),
                )
            )
        return candidates

    # ID: 7af45724-d415-4695-925a-9b0cb2b8063a
    def _collect_bindings(self) -> list[tuple[Path, str, str]]:
        """Yield (doc_path, field_name, dotted_value) for all intent bindings."""
        results: list[tuple[Path, str, str]] = []

        phases_dir = self._repo_root / ".intent" / "phases"
        if phases_dir.is_dir():
            for path in sorted(phases_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception:
                    continue
                val = data.get("implementation")
                if isinstance(val, str) and val.strip():
                    results.append((path, "implementation", val.strip()))

        mappings_dir = self._repo_root / ".intent" / "enforcement" / "mappings"
        if mappings_dir.is_dir():
            for path in sorted(mappings_dir.rglob("*.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception:
                    continue
                for val in _extract_enforced_by(data):
                    results.append((path, "enforced_by", val))

        return results

    # ID: 7424b1f1-92d3-4b38-9b24-44ab75192f20
    def _check_binding(self, dotted: str) -> str | None:
        """Return an error string if the binding is broken, else None."""
        # First token only — strips prose notes like "enum" or "method" suffixes.
        token = dotted.split()[0]
        src_file, symbol = self._resolve_module(token)
        if src_file is None:
            return f"no source file found for module path `{token}`"
        if not _symbol_in_file(src_file, symbol):
            rel = str(src_file.relative_to(self._repo_root))
            return f"symbol `{symbol}` not found in `{rel}`"
        return None

    # ID: 04fa1242-6cbf-446b-8ac2-a424462f45c7
    def _resolve_module(self, dotted: str) -> tuple[Path | None, str]:
        """Find (source_file, symbol) by trying progressively shorter module splits.

        Peels from the right: at each split point, the left side is the module
        path and the right side is the symbol name. Stops at the first split
        where the module file exists.
        """
        parts = dotted.split(".")
        for i in range(len(parts) - 1, 0, -1):
            module_parts = parts[:i]
            symbol = parts[i]
            # Try as <module>.py
            if len(module_parts) == 1:
                file_path = self._repo_root / "src" / f"{module_parts[0]}.py"
            else:
                file_path = (
                    self._repo_root
                    / "src"
                    / Path(*module_parts[:-1])
                    / f"{module_parts[-1]}.py"
                )
            if file_path.exists():
                return file_path, symbol
            # Try as <module>/__init__.py
            init_path = self._repo_root / "src" / Path(*module_parts) / "__init__.py"
            if init_path.exists():
                return init_path, symbol
        return None, parts[-1]


def _extract_enforced_by(data: object) -> list[str]:
    """Recursively collect all enforced_by string values from a YAML structure."""
    results: list[str] = []
    if isinstance(data, dict):
        for key, val in data.items():
            if key == "enforced_by" and isinstance(val, str) and val.strip():
                results.append(val.strip())
            else:
                results.extend(_extract_enforced_by(val))
    elif isinstance(data, list):
        for item in data:
            results.extend(_extract_enforced_by(item))
    return results


def _symbol_in_file(path: Path, symbol: str) -> bool:
    """Return True if symbol appears as a substring in the source file."""
    try:
        return symbol in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
