# src/shared/infrastructure/intent/intent_repository.py

"""
IntentRepository - Canonical read-only interface to CORE's Mind (.intent).

CONSTITUTIONAL FIX (V2.3.3):
- Corrected search paths to match actual tree: ['rules', 'constitution', 'phases', 'workflows'].
- Removed hallucinated 'charter/' logic.
- Maintains modularity by delegating to _IntentScanner and _RuleExtractor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from shared.config import settings
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_validator import validate_intent_tree
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


@dataclass(frozen=True)
# ID: f2a2b4e3-5947-4826-ba59-3f2e4a87e7f6
class PolicyRef:
    policy_id: str
    path: Path


@dataclass(frozen=True)
# ID: bacab865-70bc-469c-bd2b-60703de3f5ee
class RuleRef:
    rule_id: str
    policy_id: str
    source_path: Path
    content: dict[str, Any]


class _IntentScanner:
    """Specialist in finding constitutional artifacts in known directories."""

    @staticmethod
    # ID: 03ba71f4-3fb8-4b17-9431-840d060ae753
    def iter_files(root: Path, folders: list[str]) -> list[Path]:
        collected = []
        for folder in folders:
            folder_path = root / folder
            if folder_path.exists():
                for ext in ("*.yaml", "*.yml", "*.json"):
                    collected.extend(folder_path.rglob(ext))
        return sorted(collected)

    @staticmethod
    # ID: 28710b84-2ea4-4295-b491-4f8e0d797e32
    def derive_id(root: Path, file_path: Path) -> str:
        """Creates an ID based on path relative to .intent/"""
        try:
            rel = file_path.relative_to(root)
            return str(rel.with_suffix("")).replace("\\", "/")
        except ValueError:
            return file_path.stem


class _RuleExtractor:
    """Specialist in extracting rules from all CORE-recognized sections."""

    @staticmethod
    # ID: 6d92b0c9-02ae-4336-b596-2af26be1194a
    def extract(doc: dict[str, Any]) -> list[tuple[str, str, dict]]:
        results = []
        # Support sections used in your JSON and YAML files
        sections = ("rules", "principles", "safety_rules", "agent_rules")

        for section in sections:
            block = doc.get(section)
            if isinstance(block, list):
                for item in block:
                    if isinstance(item, dict):
                        rid = item.get("id") or item.get("rule_id")
                        if rid:
                            results.append((str(rid), section, item))
            elif isinstance(block, dict):
                for rid, content in block.items():
                    if isinstance(content, dict):
                        results.append((str(rid), section, content))
        return results


# ID: 04aa55aa-f275-4cce-bc73-2e5a5c50795e
class IntentRepository:
    """
    Authoritative read-only interface to the Mind.
    """

    _INDEX_LOCK = Lock()

    def __init__(self, *, strict: bool = True):
        self._root: Path = settings.MIND.resolve()
        self._strict = strict
        self._policy_index: dict[str, PolicyRef] | None = None
        self._rule_index: dict[str, RuleRef] | None = None

        validate_intent_tree(self._root, strict=self._strict)

    # ID: 596beba2-ec12-4176-9d8b-f8d7f84ed00b
    def initialize(self) -> None:
        self._ensure_index()

    @property
    # ID: 961652bc-7eb8-492a-8948-04f5a9d5e282
    def root(self) -> Path:
        return self._root

    # ID: 66653078-c59b-41bc-9254-975773755824
    def list_policies(self) -> list[PolicyRef]:
        self._ensure_index()
        return sorted(self._policy_index.values(), key=lambda r: r.policy_id)

    # ID: 708a2004-6ce3-4775-8d76-06d03f4c77d5
    def list_policy_rules(self) -> list[dict[str, Any]]:
        """Used by IntentGuard and Auditor to collect all executable law."""
        self._ensure_index()
        out = []
        for pid, pref in self._policy_index.items():
            try:
                doc = self.load_document(pref.path)
                policy_name = Path(pid).name
                for rid, section, content in _RuleExtractor.extract(doc):
                    out.append(
                        {
                            "policy_name": policy_name,
                            "section": section,
                            "rule": {**content, "id": rid},
                        }
                    )
            except Exception:
                continue
        return out

    # ID: 30ff6d03-ebae-4d92-ad1f-e05aa5f13256

    # ID: 90501a55-63c5-4a83-8720-e2a237e859a5
    def get_precedence_map(self) -> dict[str, int]:
        """
        Return policy precedence map from `.intent/constitution/precedence_rules.(yaml|yml|json)`.

        Output:
            dict[str, int] where key is policy name (stem, without suffix) and value is precedence level.
        """

        def _norm(name: str) -> str:
            return (
                name.replace(".json", "")
                .replace(".yaml", "")
                .replace(".yml", "")
                .strip()
            )

        candidates = [
            self.resolve_rel("constitution/precedence_rules.yaml"),
            self.resolve_rel("constitution/precedence_rules.yml"),
            self.resolve_rel("constitution/precedence_rules.json"),
        ]

        chosen = next((p for p in candidates if p.exists()), None)
        if not chosen:
            return {}

        data = self.load_document(chosen)
        hierarchy = data.get("policy_hierarchy", [])
        if not isinstance(hierarchy, list):
            if self._strict:
                from shared.infrastructure.intent.errors import GovernanceError

                raise GovernanceError(
                    f"Invalid precedence_rules format (policy_hierarchy not a list): {chosen}"
                )
            logger.warning(
                "Invalid precedence_rules format (policy_hierarchy not a list): %s",
                chosen,
            )
            return {}

        mapping: dict[str, int] = {}
        for entry in hierarchy:
            if not isinstance(entry, dict):
                continue

            level_raw = entry.get("level", 999)
            try:
                level = int(level_raw)
            except Exception:
                level = 999

            if isinstance(entry.get("policy"), str):
                mapping[_norm(entry["policy"])] = level

            if isinstance(entry.get("policies"), list):
                for p in entry["policies"]:
                    if isinstance(p, str):
                        mapping[_norm(p)] = level

        return mapping

    # ID: e02747ba-8ea3-4ffd-a635-a5b9894e36d9
    def get_rule(self, rule_id: str) -> RuleRef:
        self._ensure_index()
        ref = self._rule_index.get(rule_id)
        if not ref:
            raise GovernanceError(f"Rule ID not found: {rule_id}")
        return ref

    # ID: c7ed2edc-a53d-482c-aff4-2b982baf933a
    def load_policy(self, policy_id: str) -> dict[str, Any]:
        self._ensure_index()
        ref = self._policy_index.get(policy_id)
        if not ref:
            raise GovernanceError(f"Policy ID not found: {policy_id}")
        return self.load_document(ref.path)

    def _ensure_index(self) -> None:
        if self._policy_index is not None:
            return

        with self._INDEX_LOCK:
            if self._policy_index is not None:
                return

            logger.info("Indexing Mind at %s...", self._root)
            p_index, r_index = {}, {}

            # 1. SCAN THE ACTUAL DIRECTORIES SHOWN IN TREE
            active_folders = ["rules", "constitution", "phases", "workflows", "META"]
            for path in _IntentScanner.iter_files(self._root, active_folders):
                pid = _IntentScanner.derive_id(self._root, path)
                p_index[pid] = PolicyRef(policy_id=pid, path=path)

            # 2. EXTRACT RULES (Building Cross-Policy Index)
            for pid, pref in p_index.items():
                try:
                    doc = self.load_document(pref.path)
                    for rid, _, content in _RuleExtractor.extract(doc):
                        r_index[rid] = RuleRef(rid, pid, pref.path, content)
                except Exception:
                    continue

            self._policy_index, self._rule_index = p_index, r_index
            logger.info(
                "✅ Mind Indexed: %d artifacts, %d rules", len(p_index), len(r_index)
            )

    # ID: 86c75c4d-8686-42fb-86c3-26bb0d2d45b3
    def load_document(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise GovernanceError(f"Artifact missing: {path}")
        if path.suffix in (".yaml", ".yml"):
            return strict_yaml_processor.load_strict(path)
        return json.loads(path.read_text("utf-8")) if path.suffix == ".json" else {}

    # ID: d51bd39e-82b0-4786-8bbc-c4cf1ec57f96
    def resolve_rel(self, rel: str | Path) -> Path:
        resolved = (self._root / Path(rel)).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise GovernanceError(f"Security: Blocked path traversal for {rel}")
        return resolved


# Global Singleton
_INTENT_REPO: IntentRepository | None = None


# ID: d9f1e5c3-86ab-4d40-829d-9030b5594944
def get_intent_repository() -> IntentRepository:
    global _INTENT_REPO
    if _INTENT_REPO is None:
        _INTENT_REPO = IntentRepository()
    return _INTENT_REPO
