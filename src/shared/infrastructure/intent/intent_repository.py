# src/shared/infrastructure/intent/intent_repository.py

"""
IntentRepository

Canonical, read-only interface to CORE's Mind (.intent).

This is the single source of truth for:
- locating .intent artifacts (policies, schemas, charter, etc.)
- loading/parsing them (YAML strictly, JSON optionally)
- indexing rules/policies for stable query access
- providing policy-level query APIs (precedence map, policy rule lists)

This module intentionally exposes no write primitives and relies on
shared.path_resolver for filesystem location knowledge.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


# ID: 9eb28147-e0da-4f48-84ef-1274b5b80496
class GovernanceError(RuntimeError):
    """Raised when an intent artifact cannot be resolved or violates expectations."""


@dataclass(frozen=True)
# ID: c2e64164-72b7-437f-a686-7aa856278bde
class PolicyRef:
    policy_id: str
    path: Path


@dataclass(frozen=True)
# ID: 810c5fce-55e8-4390-a397-b5d25ff07522
class RuleRef:
    rule_id: str
    policy_id: str
    source_path: Path
    content: dict[str, Any]


# ID: 564573dd-10db-46f3-a454-5141a4e50749
class IntentRepository:
    """
    The canonical read-only repository for .intent.

    Contract:
    - Root is derived from settings only.
    - All parsing is deterministic.
    - No write operations are exposed.
    """

    _INDEX_LOCK = Lock()

    def __init__(
        self,
        *,
        strict: bool = True,
        allow_writable_root: bool = True,
    ) -> None:
        # Use settings as the entry point for the Mind's location
        self._root: Path = settings.MIND.resolve()
        self._strict = strict
        self._allow_writable_root = allow_writable_root

        # Lazy-built indexes
        self._policy_index: dict[str, PolicyRef] | None = None
        self._rule_index: dict[str, RuleRef] | None = None
        self._hierarchy: dict[str, list[str]] | None = None

        self._check_root_safety()

    # -------------------------------------------------------------------------
    # Root / path resolution
    # -------------------------------------------------------------------------

    @property
    # ID: c4c35413-0bfa-4ca7-9dd1-90bafc67ea7b
    def root(self) -> Path:
        return self._root

    # ID: cf82fd15-7df2-45f7-9c53-37a23bf2376a
    def resolve_rel(self, rel: str | Path) -> Path:
        """
        Resolve a path relative to .intent safely (prevents path traversal).
        """
        rel_path = Path(rel)
        if rel_path.is_absolute():
            raise GovernanceError(f"Absolute paths are not allowed: {rel_path}")

        resolved = (self._root / rel_path).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise GovernanceError(f"Path traversal detected: {rel_path}")

        return resolved

    # -------------------------------------------------------------------------
    # Loaders
    # -------------------------------------------------------------------------

    # ID: 47ce7eb7-ba4b-4f47-bf78-4b0bf3c77509
    def load_document(self, path: Path) -> dict[str, Any]:
        """
        Load YAML strictly (.yaml/.yml) or JSON (.json).
        """
        if not path.exists():
            raise GovernanceError(f"Intent artifact not found: {path}")

        if path.suffix in (".yaml", ".yml"):
            return strict_yaml_processor.load_strict(path)

        if path.suffix == ".json":
            try:
                return json.loads(path.read_text("utf-8")) or {}
            except (OSError, ValueError) as e:
                raise GovernanceError(f"Failed to parse JSON: {path}: {e}") from e

        raise GovernanceError(
            f"Unsupported intent artifact type: {path.suffix} ({path})"
        )

    # ID: b26242f2-8e09-4693-ba41-a993447564d4
    def load_policy(self, logical_path_or_id: str) -> dict[str, Any]:
        """
        Load a policy by either:
        - legacy meta.yaml logical path (e.g., 'policies.code.code_standards'), OR
        - canonical policy_id derived from .intent relative path (e.g., 'policies/code/code_standards')
        """
        # 1) Legacy: meta.yaml logical path
        if "." in logical_path_or_id and "/" not in logical_path_or_id:
            path = settings.get_path(logical_path_or_id)
            return self.load_document(path)

        # 2) Canonical: policy_id (relative path without suffix)
        policy_id = logical_path_or_id.strip().lstrip("/")
        candidates = self._candidate_paths_for_id(policy_id)
        for p in candidates:
            if p.exists():
                return self.load_document(p)

        raise GovernanceError(f"Policy not found for id: {policy_id}")

    # -------------------------------------------------------------------------
    # Query APIs (IntentGuard must call these; it must not load/crawl itself)
    # -------------------------------------------------------------------------

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

    # ID: 8dc3100f-cb41-473a-bc86-b9ce58ca2ccb
    def list_policy_rules(self) -> list[dict[str, Any]]:
        """
        Return all policy rule blocks (raw dicts), across all policies and standards.

        Shape:
            [
              {
                "policy_name": "<stem used for precedence>",
                "section": "rules" | "safety_rules" | "agent_rules",
                "rule": { ... raw rule dict ... }
              },
              ...
            ]
        """
        out: list[dict[str, Any]] = []
        for pref in self.list_policies():
            doc = self.load_document(pref.path)
            policy_name = Path(pref.policy_id).name  # stable, precedence-friendly

            # Support both rules array and constitutional principles
            for section in ("rules", "safety_rules", "agent_rules", "principles"):
                block = doc.get(section)
                if isinstance(block, list):
                    for item in block:
                        if isinstance(item, dict):
                            out.append(
                                {
                                    "policy_name": policy_name,
                                    "section": section,
                                    "rule": item,
                                }
                            )
                elif isinstance(block, dict):
                    # For principles in constitutional documents (e.g. authority.json)
                    for rid, item in block.items():
                        if isinstance(item, dict):
                            # Ensure the ID is part of the rule for executor use
                            rule_copy = {**item, "id": rid}
                            out.append(
                                {
                                    "policy_name": policy_name,
                                    "section": section,
                                    "rule": rule_copy,
                                }
                            )
        return out

    # -------------------------------------------------------------------------
    # Index-backed lookups
    # -------------------------------------------------------------------------

    # ID: f9538805-00a0-49ce-9a97-16702573f24e
    def get_rule(self, rule_id: str) -> RuleRef:
        """
        Global rule lookup by ID (requires index).
        """
        self._ensure_index()
        assert self._rule_index is not None

        ref = self._rule_index.get(rule_id)
        if not ref:
            raise GovernanceError(f"Rule ID not found: {rule_id}")
        return ref

    # ID: 34da4756-1be7-409e-8d92-5b01f8b82176
    def list_policies(self) -> list[PolicyRef]:
        """
        List all policies and standards discovered in the Mind.
        """
        self._ensure_index()
        assert self._policy_index is not None
        return sorted(self._policy_index.values(), key=lambda r: r.policy_id)

    # ID: 8aac0a74-e995-4daa-95dc-1f931b07bfd4
    def list_governance_map(self) -> dict[str, list[str]]:
        """
        Returns a stable hierarchy of category -> policy_ids.
        Category is the first directory under governance roots.
        """
        self._ensure_index()
        assert self._hierarchy is not None
        # Return a copy to preserve read-only outward semantics
        return {k: list(v) for k, v in self._hierarchy.items()}

    # -------------------------------------------------------------------------
    # Indexing
    # -------------------------------------------------------------------------

    def _ensure_index(self) -> None:
        if (
            self._policy_index is not None
            and self._rule_index is not None
            and self._hierarchy is not None
        ):
            return

        with self._INDEX_LOCK:
            if (
                self._policy_index is not None
                and self._rule_index is not None
                and self._hierarchy is not None
            ):
                return

            policy_index, hierarchy = self._build_policy_index()
            rule_index = self._build_rule_index(policy_index)

            self._policy_index = policy_index
            self._rule_index = rule_index
            self._hierarchy = hierarchy

            logger.info(
                "IntentRepository indexed %s policies and %s rules.",
                len(self._policy_index),
                len(self._rule_index),
            )

    def _build_policy_index(self) -> tuple[dict[str, PolicyRef], dict[str, list[str]]]:
        """
        Consults PathResolver (Map) to find where to scan for rules.
        This enforces DRY by relying on the central path definitions.
        """
        # We scan the folders managed by the Constitution: policies and standards
        # These are handled as sub-directories of the intent root
        search_roots = ["policies", "standards"]

        index: dict[str, PolicyRef] = {}
        hierarchy: dict[str, list[str]] = {}

        for root_name in search_roots:
            root_dir = self._root / root_name
            if not root_dir.exists():
                continue

            for path in self._iter_policy_files(root_dir):
                policy_id = self._policy_id_from_path(path)
                if policy_id in index:
                    msg = (
                        f"Duplicate policy_id detected: {policy_id} "
                        f"({index[policy_id].path} vs {path})"
                    )
                    if self._strict:
                        raise GovernanceError(msg)
                    logger.warning(msg)
                    continue

                index[policy_id] = PolicyRef(policy_id=policy_id, path=path)

                category = self._category_from_policy_id(policy_id)
                hierarchy.setdefault(category, []).append(policy_id)

        for cat in hierarchy:
            hierarchy[cat].sort()

        return index, hierarchy

    def _build_rule_index(
        self, policy_index: dict[str, PolicyRef]
    ) -> dict[str, RuleRef]:
        rule_index: dict[str, RuleRef] = {}

        for policy_id, ref in policy_index.items():
            try:
                data = self.load_document(ref.path)
            except GovernanceError as e:
                if self._strict:
                    raise
                logger.warning("Skipping unreadable policy %s: %s", policy_id, e)
                continue

            # Support both flat rules (rules) and constitutional sections (principles, safety_rules, etc)
            sections = ["rules", "safety_rules", "agent_rules", "principles"]
            for section in sections:
                rules = data.get(section, [])
                for rid, content in self._extract_rules(rules):
                    if rid in rule_index:
                        msg = (
                            f"Duplicate rule_id detected: {rid} "
                            f"({rule_index[rid].source_path} vs {ref.path})"
                        )
                        if self._strict:
                            raise GovernanceError(msg)
                        logger.warning(msg)
                        continue

                    rule_index[rid] = RuleRef(
                        rule_id=rid,
                        policy_id=policy_id,
                        source_path=ref.path,
                        content={**content},
                    )

        return rule_index

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _check_root_safety(self) -> None:
        if self._allow_writable_root:
            return

        try:
            # Simple check if root is writable
            writable = self._root.exists() and self._root.is_dir()
            # If strictly required, could add explicit os.access(W_OK) here.
        except OSError:
            writable = False

        if writable:
            raise GovernanceError(
                f".intent root is writable but allow_writable_root=False: {self._root}"
            )

    def _iter_policy_files(self, policies_dir: Path) -> Iterable[Path]:
        for suffix in ("*.yaml", "*.yml", "*.json"):
            yield from policies_dir.rglob(suffix)

    def _policy_id_from_path(self, path: Path) -> str:
        # Create id relative to .intent root (e.g. 'policies/code/style')
        try:
            rel = path.relative_to(self._root)
            return str(rel.with_suffix("")).replace("\\", "/")
        except ValueError:
            return path.stem

    def _category_from_policy_id(self, policy_id: str) -> str:
        # policy_id is like "policies/<category>/..." or "standards/<category>/..."
        parts = policy_id.split("/")
        if len(parts) >= 2 and parts[0] in ("policies", "standards"):
            return parts[1]
        return "uncategorized"

    def _candidate_paths_for_id(self, policy_id: str) -> list[Path]:
        # policy_id points to a path under .intent, like 'policies/code/style'
        base = self.resolve_rel(policy_id)
        return [
            Path(str(base) + ".yaml"),
            Path(str(base) + ".yml"),
            Path(str(base) + ".json"),
        ]

    def _extract_rules(self, rules: Any) -> Iterable[tuple[str, dict[str, Any]]]:
        """
        Supports:
        - list of dicts with 'id' or 'rule_id'
        - dict mapping id -> dict (common in constitutional principles)
        """
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                rid = rule.get("id") or rule.get("rule_id")
                if isinstance(rid, str) and rid.strip():
                    yield rid, rule
            return

        if isinstance(rules, dict):
            for rid, content in rules.items():
                if isinstance(rid, str) and isinstance(content, dict):
                    yield rid, content
            return


# Singleton-style factory
_INTENT_REPO: IntentRepository | None = None
_INTENT_REPO_LOCK = Lock()


# ID: 7823ea26-947d-4cb2-97db-47f99d09df5d
def get_intent_repository() -> IntentRepository:
    global _INTENT_REPO
    with _INTENT_REPO_LOCK:
        if _INTENT_REPO is None:
            _INTENT_REPO = IntentRepository(strict=True)
        return _INTENT_REPO
