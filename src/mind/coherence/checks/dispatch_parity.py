# src/mind/coherence/checks/dispatch_parity.py
"""DISPATCH_PARITY — rules-to-dispatch edge coverage check.

Per ADR-136 D2. Detects two gap classes that the ADR-073 D3 check taxonomy
does not cover:

  UNMAPPED   — a rule ID in .intent/rules/ has no entry in
               .intent/enforcement/mappings/. Closing these closes the
               ADR-066 unmapped-rules invariant.

  UNKNOWN_ENGINE — a mapping entry whose ``engine`` value is neither a
               file-backed engine discovered by EngineRegistry nor an entry
               in .intent/taxonomies/substrate_enforcement.yaml. Catches
               typos and taxonomy drift before they silently no-op.

No LLM. No vectors. Pure YAML/JSON data reading.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .base import CoherenceCandidate


if TYPE_CHECKING:
    from shared.infrastructure.intent.intent_repository import IntentRepository


# ID: 0804a181-d8ea-4d6d-9552-9dffba1ffcd4
class DispatchParityCheck:
    """CCC check class for ADR-136 D2 rules-to-dispatch parity."""

    relation = "DISPATCH_PARITY"

    # ID: 0383fa90-16a6-4556-b16b-9cd78cbf49ff
    def __init__(self, repo_root: Path, intent_repo: IntentRepository) -> None:
        self._repo_root = Path(repo_root)
        self._intent_repo = intent_repo

    # ID: 0349a8d5-13ee-4c3d-afcc-fbdca1b7b23b
    async def run(self) -> list[CoherenceCandidate]:
        rule_ids = self._load_rule_ids()
        mapping_keys, mapping_engines = self._load_mappings()
        substrate_engines = self._load_substrate_taxonomy()
        file_backed_engines = self._derive_file_backed_engines()

        candidates: list[CoherenceCandidate] = []

        # Sub-check A: UNMAPPED — rules with no mapping entry
        for rule_id in sorted(rule_ids - mapping_keys):
            candidates.append(
                CoherenceCandidate(
                    relation=self.relation,
                    documents=[".intent/rules/", ".intent/enforcement/mappings/"],
                    claim=f"UNMAPPED: rule '{rule_id}' has no enforcement mapping entry",
                    rationale=(
                        "ADR-066 requires every active rule to have an entry in "
                        "auto_remediation.yaml and a mapping in enforcement/mappings/. "
                        "An unmapped rule is invisible to the coherence surface and "
                        "cannot route findings to the governor inbox."
                    ),
                )
            )

        # Sub-check B: UNKNOWN_ENGINE — mapping engine not in registry or substrate taxonomy
        known_engines = file_backed_engines | substrate_engines | {"passive_gate"}
        for rule_id, engine in sorted(mapping_engines.items()):
            if engine not in known_engines:
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[
                            ".intent/enforcement/mappings/",
                            ".intent/taxonomies/substrate_enforcement.yaml",
                        ],
                        claim=(
                            f"UNKNOWN_ENGINE: mapping for '{rule_id}' "
                            f"references engine '{engine}' which is neither "
                            "a file-backed engine nor a substrate taxonomy entry"
                        ),
                        rationale=(
                            "EngineRegistry.get() raises ValueError for unknown engine IDs "
                            "unless they are in PASSIVE_ALIASES. An unlisted engine silently "
                            "no-ops or raises at audit time. Per ADR-136, every passive-routed "
                            "engine MUST appear in substrate_enforcement.yaml."
                        ),
                    )
                )

        return candidates

    def _load_rule_ids(self) -> set[str]:
        return self._intent_repo.known_rule_ids()

    def _load_mappings(self) -> tuple[set[str], dict[str, str]]:
        mapping_keys: set[str] = set()
        mapping_engines: dict[str, str] = {}
        for path, data in self._intent_repo.iter_documents():
            parts = path.parts
            if "enforcement" not in parts or "mappings" not in parts:
                continue
            if path.suffix not in (".yaml", ".yml"):
                continue
            entries = data.get("mappings", {})
            if isinstance(entries, dict):
                for rule_id, entry in entries.items():
                    if isinstance(rule_id, str) and not rule_id.startswith("#"):
                        mapping_keys.add(rule_id)
                        if isinstance(entry, dict) and "engine" in entry:
                            mapping_engines[rule_id] = entry["engine"]
        return mapping_keys, mapping_engines

    def _load_substrate_taxonomy(self) -> set[str]:
        taxonomy_path = (
            self._repo_root / ".intent" / "taxonomies" / "substrate_enforcement.yaml"
        )
        try:
            data = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
            entries = data.get("entries", {})
            if isinstance(entries, dict):
                return set(entries.keys())
        except Exception:
            pass
        return set()

    def _derive_file_backed_engines(self) -> set[str]:
        engines_dir = self._repo_root / "src" / "mind" / "logic" / "engines"
        names: set[str] = set()
        for path in engines_dir.iterdir():
            if path.suffix == ".py" and not path.name.startswith("_"):
                names.add(path.stem)
        return names
