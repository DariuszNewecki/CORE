# src/shared/infrastructure/intent/intent_repository.py

"""
IntentRepository - Canonical read-only interface to CORE's Mind (.intent).

CONSTITUTIONAL FIX (V2.3.0):
- Corrected search paths to match actual tree: ['rules', 'constitution', 'phases', 'workflows'].
- Removed hallucinated 'charter/' logic.
- Maintains modularity by delegating to _IntentScanner and _RuleExtractor.

CONSTITUTIONAL FIX (V2.4.0):
- Removed hardcoded search_roots list in _build_policy_index.
- IntentRepository now reads active directories from META/intent_tree.yaml.
- Adding a new .intent/ directory is now a constitutional act, not a Python change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from shared.config import settings
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_validator import validate_intent_tree
from shared.infrastructure.rooted_repository import RootedRepository
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)

CORE_ROLE = "facade"  # ADR-095 D3


@dataclass(frozen=True)
# ID: cfe1ab6c-7706-41e1-bf99-18359a12849c
class PolicyRef:
    policy_id: str
    path: Path


@dataclass(frozen=True)
# ID: a1b079ad-ce37-4efb-8558-57ce7995362a
class RuleRef:
    rule_id: str
    policy_id: str
    source_path: Path
    content: dict[str, Any]
    rule_content_hash: str


@dataclass(frozen=True)
# ID: 1144e885-b01b-4045-a2a9-6393606e0981
class ArtifactTypeRef:
    """A loaded artifact-type declaration from .intent/artifact_types/.

    Per ADR-090 D1, artifact types are first-class constitutional declarations
    with their own META schema (artifact_type.schema.json). The full content
    dict is preserved so consumers can read any declared field without the
    repository needing to know about each one.
    """

    id: str
    path: Path
    content: dict[str, Any]


# ID: 7c4e8b2f-1d6a-49f3-b0e8-3a5c8d4e9f1b
def compute_rule_content_hash(content: dict[str, Any]) -> str:
    """SHA-256 over a canonicalised rule body, for ADR-044 cache keying.

    JSON serialisation with ``sort_keys=True`` + compact separators is
    deterministic: identical rule semantics produce identical bytes
    regardless of YAML cosmetic differences (key reordering, comment
    reformatting, blank lines). The YAML→dict load step already strips
    comments and normalises scalar representation, so the JSON re-encode
    is sufficient to capture every governance-meaningful field.
    """
    canonical = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ID: 698141bd-6440-4ffa-950b-a547ecee4699
class IntentRepository(RootedRepository):
    """
    The canonical read-only repository for .intent.

    Contract:
    - Root is derived from settings only.
    - All parsing is deterministic.
    - No write operations are exposed.
    - Active directory list is read from META/intent_tree.yaml — never hardcoded.
    - root + resolve_rel come from RootedRepository (issue #128 dedup).
    """

    _INDEX_LOCK = Lock()

    def __init__(
        self,
        *,
        strict: bool = True,
        allow_writable_root: bool = True,
        root: Path | None = None,
    ) -> None:
        self._root: Path = (
            root.resolve() if root is not None else settings.MIND.resolve()
        )
        self._strict = strict
        self._allow_writable_root = allow_writable_root

        self._policy_index: dict[str, PolicyRef] | None = None
        self._rule_index: dict[str, RuleRef] | None = None
        self._hierarchy: dict[str, list[str]] | None = None
        self._artifact_type_index: dict[str, ArtifactTypeRef] | None = None

        self._check_root_safety()
        validate_intent_tree(self._root, strict=self._strict)

    # ID: ab9383d3-df49-4565-856b-c3d8846b405d
    def initialize(self) -> None:
        self._ensure_index()

    # ID: 4a91e5f0-2d8c-4b3e-91a7-c5b8d3e9f2a1
    def reload(self) -> None:
        """Drop the cached index and rebuild from disk.

        Called once per audit-sensor cycle (ADR-039) so policies and
        rules added to .intent/ after daemon boot become enforceable
        without a process restart. Re-emits the "indexed N policies and
        M rules" log line so cycle-to-cycle drift is visible in journald.
        """
        with self._INDEX_LOCK:
            self._policy_index = None
            self._rule_index = None
            self._hierarchy = None
            self._artifact_type_index = None
        self._ensure_index()

    # ID: 57f50f3a-fc99-4e47-9ddf-24da5f105863
    def load_document(self, path: Path) -> dict[str, Any]:
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

    # ID: 1d4f9c2a-7e83-4b15-9a6e-3c8d5f0a1b27
    def iter_documents(
        self,
        *,
        skip_components: Iterable[str] = (),
    ) -> Iterator[tuple[Path, dict[str, Any]]]:
        """Yield (absolute_path, parsed_dict) for every .yaml/.yml/.json under .intent/.

        Canonical gateway for corpus-walking callers (e.g. the governance
        claim harvester) that previously did `intent_root.rglob(...)` —
        replaces direct Path access per architecture.namespace.no_direct_protected_access
        (renamed #490; formerly architecture.intent.non_gateway_no_direct_resolution).

        skip_components filters by path component name (e.g. {"META"} to
        exclude .intent/META/**). Parse failures are logged and skipped so
        a single bad file does not abort the walk.
        """
        skip = frozenset(skip_components)
        for path in self._iter_policy_files(self._root):
            if skip and any(part in skip for part in path.parts):
                continue
            try:
                yield path, self.load_document(path)
            except GovernanceError as exc:
                logger.warning("iter_documents: skipping %s: %s", path, exc)

    # ID: 9cb968d7-d78f-4161-8c87-6d606e7bc66a
    def iter_flow_documents(self) -> Iterator[tuple[Path, dict[str, Any]]]:
        """Yield (absolute_path, parsed_dict) for every flow declaration in .intent/flows/.

        Callers (e.g. FlowRegistry) MUST use this method rather than directly
        globbing .intent/flows/ — routes all .intent/ access through the shared
        infrastructure boundary per architecture.namespace.no_direct_protected_access.
        Parse failures are logged and skipped; a single bad file does not abort the walk.
        """
        flows_dir = self.resolve_rel("flows")
        if not flows_dir.exists():
            return
        for path in sorted(self._iter_policy_files(flows_dir)):
            try:
                yield path, self.load_document(path)
            except GovernanceError as exc:
                logger.warning("iter_flow_documents: skipping %s: %s", path, exc)

    # ID: a2b3c4d5-e6f7-8901-abcd-ef1234567890
    def load_text(self, rel: str | Path) -> str:
        """
        Load a raw text artifact from .intent/ (e.g. markdown files).
        Enforces boundary — path must be within intent root.
        Read-only. No parsing.
        """
        abs_path = self.resolve_rel(rel)
        if not abs_path.exists():
            raise GovernanceError(f"Intent text artifact not found: {abs_path}")
        try:
            return abs_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            raise GovernanceError(
                f"Failed to read text artifact {abs_path}: {e}"
            ) from e

    # ID: 352c67ce-9d90-4ab2-944c-e6ef3622b411
    def load_policy(self, logical_path_or_id: str) -> dict[str, Any]:
        if "." in logical_path_or_id and "/" not in logical_path_or_id:
            path = settings.get_path(logical_path_or_id)
            return self.load_document(path)

        policy_id = logical_path_or_id.strip().lstrip("/")
        candidates = self._candidate_paths_for_id(policy_id)
        for p in candidates:
            if p.exists():
                return self.load_document(p)

        raise GovernanceError(f"Policy not found for id: {policy_id}")

    # ID: 375428ca-11be-4c31-b12b-9e0f7c11b766
    def list_workflows(self) -> list[str]:
        base = self.resolve_rel("workflows/definitions")
        if not base.exists():
            return []

        out: list[str] = []
        for path in self._iter_policy_files(base):
            try:
                rel = path.relative_to(self._root)
                out.append(str(rel.with_suffix("")).replace("\\", "/"))
            except ValueError:
                continue

        return sorted(out)

    # ID: 06c6ab43-78ba-4ab0-8bf1-fb21c68a86e4
    def load_workflow(self, workflow_id: str) -> dict[str, Any]:
        workflow_id = workflow_id.strip().lstrip("/")

        candidates: list[Path] = []
        if "/" in workflow_id:
            candidates.extend(self._candidate_paths_for_id(workflow_id))
        else:
            candidates.extend(
                self._candidate_paths_for_id(f"workflows/definitions/{workflow_id}")
            )

        for path in candidates:
            if path.exists():
                return self.load_document(path)

        raise GovernanceError(f"Workflow not found: {workflow_id}")

    # ID: 6b7f77ac-6504-4740-bd99-de389c76a46c
    def list_workers(self) -> list[str]:
        """List all constitutionally declared worker IDs from .intent/workers/."""
        base = self.resolve_rel("workers")
        if not base.exists():
            return []
        out: list[str] = []
        for path in self._iter_policy_files(base):
            try:
                rel = path.relative_to(self._root)
                out.append(str(rel.with_suffix("")).replace("\\", "/"))
            except ValueError:
                continue
        return sorted(out)

    # ID: 3ce78dc7-6090-42b3-97ca-ec7c61b0d7f4
    def load_worker(self, worker_id: str) -> dict[str, Any]:
        """Load a worker declaration by its canonical ID (e.g. 'workers/my_worker')."""
        worker_id = worker_id.strip().lstrip("/")
        candidates = self._candidate_paths_for_id(worker_id)
        for path in candidates:
            if path.exists():
                return self.load_document(path)
        raise GovernanceError(f"Worker declaration not found: {worker_id}")

    # ID: de413c80-9e66-4d70-89e7-8f81a522aac5
    def list_phases(self) -> list[str]:
        base = self.resolve_rel("phases")
        if not base.exists():
            return []

        out: list[str] = []
        for path in self._iter_policy_files(base):
            try:
                rel = path.relative_to(self._root)
                out.append(str(rel.with_suffix("")).replace("\\", "/"))
            except ValueError:
                continue

        return sorted(out)

    # ID: d800d3eb-f2b2-405e-9aa3-103f3522bec1
    def load_phase(self, phase_id: str) -> dict[str, Any]:
        phase_id = phase_id.strip().lstrip("/")

        candidates: list[Path] = []
        if "/" in phase_id:
            candidates.extend(self._candidate_paths_for_id(phase_id))
        else:
            candidates.extend(self._candidate_paths_for_id(f"phases/{phase_id}"))

        for path in candidates:
            if path.exists():
                return self.load_document(path)

        raise GovernanceError(f"Phase not found: {phase_id}")

    # ID: fbf369e2-222a-4961-867f-eca2bec01232
    def get_precedence_map(self) -> dict[str, int]:
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

    # ID: e0bffd8f-e87a-40bb-927e-97ec69dfc7e7
    def list_policy_rules(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for pref in self.list_policies():
            doc = self.load_document(pref.path)
            policy_name = Path(pref.policy_id).name

            for section in ("rules", "safety_rules", "agent_rules", "principles"):
                block = doc.get(section)
                if isinstance(block, list):
                    for item in block:
                        if isinstance(item, dict):
                            out.append(
                                {
                                    "policy_name": policy_name,
                                    "policy_id": pref.policy_id,
                                    "section": section,
                                    "rule": item,
                                }
                            )
                elif isinstance(block, dict):
                    for rid, item in block.items():
                        if isinstance(item, dict):
                            rule_copy = {**item, "id": rid}
                            out.append(
                                {
                                    "policy_name": policy_name,
                                    "policy_id": pref.policy_id,
                                    "section": section,
                                    "rule": rule_copy,
                                }
                            )
        return out

    # ID: 4f068efb-842b-4555-9201-820c9617a90c
    def find_rules(
        self,
        *,
        phase: str | None = None,
        authority: str | None = None,
        policy_ids: list[str] | None = None,
        sections: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return normalized rules filtered by constitutional selectors.

        Notes:
        - phase/authority matching is case-insensitive
        - policy_ids may be full ids or leaf names
        - rules without explicit phase/authority can still be included when the
          corresponding filter is not requested
        """
        requested_policy_ids = {p.strip().strip("/") for p in (policy_ids or []) if p}
        requested_policy_names = {Path(p).name for p in requested_policy_ids}
        requested_sections = set(sections or [])

        phase_norm = phase.lower() if phase else None
        authority_norm = authority.lower() if authority else None

        matches: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for entry in self.list_policy_rules():
            entry_policy_id = str(entry.get("policy_id", "")).strip("/")
            entry_policy_name = str(entry.get("policy_name", "")).strip()
            entry_section = str(entry.get("section", "")).strip()
            raw_rule = entry.get("rule", {})

            if not isinstance(raw_rule, dict):
                continue

            if requested_sections and entry_section not in requested_sections:
                continue

            if requested_policy_ids:
                if (
                    entry_policy_id not in requested_policy_ids
                    and entry_policy_name not in requested_policy_names
                ):
                    continue

            normalized = dict(raw_rule)
            normalized.setdefault("id", normalized.get("rule_id"))
            normalized.setdefault("policy_id", entry_policy_id)
            normalized.setdefault("policy_name", entry_policy_name)
            normalized.setdefault("section", entry_section)

            rule_phase = self._extract_rule_phase(normalized)
            rule_authority = self._extract_rule_authority(normalized)

            if phase_norm and rule_phase and rule_phase.lower() != phase_norm:
                continue

            if (
                authority_norm
                and rule_authority
                and rule_authority.lower() != authority_norm
            ):
                continue

            if rule_phase:
                normalized["phase"] = rule_phase
            if rule_authority:
                normalized["authority"] = rule_authority

            identity = (
                str(normalized.get("id") or ""),
                str(normalized.get("policy_id") or ""),
                str(normalized.get("section") or ""),
            )
            if identity in seen:
                continue

            seen.add(identity)
            matches.append(normalized)

        return matches

    # ID: fd0975cb-d854-4491-8268-2c9a3f3595e6
    def get_rule(self, rule_id: str) -> RuleRef:
        self._ensure_index()
        assert self._rule_index is not None

        ref = self._rule_index.get(rule_id)
        if not ref:
            raise GovernanceError(f"Rule ID not found: {rule_id}")
        return ref

    # ID: 91baba20-e413-410f-a98e-66dc38732138
    def known_rule_ids(self) -> set[str]:
        """Return the set of every rule ID currently in the active registry.

        The authoritative "does this rule still exist?" source. Used by the
        retired-rule finding sweep (#657): a finding whose rule id is absent
        from this set is an orphan (its rule was renamed/retired and the audit
        sensor's resolution pass — which keys on live rule ids — can never
        clear it). Derived from `_rule_index` at call time, so it tracks
        adds/removes automatically. A non-empty result is the sweep's
        fail-closed precondition: an empty set means the registry failed to
        load, and the caller MUST NOT sweep.
        """
        self._ensure_index()
        assert self._rule_index is not None
        return set(self._rule_index)

    # ID: c3b33ec1-97ec-419e-8969-1c5da96ca7d2
    def rule_namespaces(self) -> set[str]:
        """Return the set of top-level dot segments across all known rule IDs.

        Derived from `_rule_index` at call time — adding a rule to a new
        namespace (e.g. dropping a `purity.docstrings.required` rule into a
        previously-empty `purity` directory) automatically grows the set.

        ADR-091 D5 Phase 3 / Phase 5 consumer-distinction predicates read this
        method to derive which `<sub_namespace>` segments of the canonical
        `python::<sub_namespace>::<identity>` subject format belong to an
        audit-violation sensor versus a test/coherence sensor.
        """
        self._ensure_index()
        assert self._rule_index is not None
        return {rid.split(".", 1)[0] for rid in self._rule_index}

    # ID: cb11d848-d66e-4b2b-b076-7489c4670059
    def list_policies(self) -> list[PolicyRef]:
        self._ensure_index()
        assert self._policy_index is not None
        return sorted(self._policy_index.values(), key=lambda r: r.policy_id)

    # ID: 67cb646c-80dc-417e-a0b7-efcc7b626a92
    def list_governance_map(self) -> dict[str, list[str]]:
        self._ensure_index()
        assert self._hierarchy is not None
        return {k: list(v) for k, v in self._hierarchy.items()}

    # ID: 3a1b4d07-980d-4869-b512-3c57fbb85297
    def list_artifact_types(self) -> list[ArtifactTypeRef]:
        """Return all loaded artifact-type declarations, sorted by id.

        Per ADR-090 D1, artifact types declare how CORE governs each class
        of artifact. The list is the authoritative answer to "what artifact
        classes does this CORE instance know about?".
        """
        self._ensure_index()
        assert self._artifact_type_index is not None
        return sorted(self._artifact_type_index.values(), key=lambda r: r.id)

    # ID: f41ea217-1027-4923-afca-bdba87069f1f
    def get_artifact_type(self, artifact_type_id: str) -> ArtifactTypeRef:
        """Look up a single artifact-type declaration by its `id`.

        Raises GovernanceError if no declaration with that id is registered.
        """
        self._ensure_index()
        assert self._artifact_type_index is not None
        ref = self._artifact_type_index.get(artifact_type_id)
        if ref is None:
            raise GovernanceError(
                f"Unknown artifact_type id: {artifact_type_id!r}. "
                f"Registered: {sorted(self._artifact_type_index.keys())}"
            )
        return ref

    def _ensure_index(self) -> None:
        if (
            self._policy_index is not None
            and self._rule_index is not None
            and self._hierarchy is not None
            and self._artifact_type_index is not None
        ):
            return

        with self._INDEX_LOCK:
            if (
                self._policy_index is not None
                and self._rule_index is not None
                and self._hierarchy is not None
                and self._artifact_type_index is not None
            ):
                return

            policy_index, hierarchy = self._build_policy_index()
            rule_index = self._build_rule_index(policy_index)
            artifact_type_index = self._build_artifact_type_index()

            # ADR-120 D3: cross-validate supported_sensors ↔ worker declarations
            # before committing the index. Fail closed in strict mode.
            self._validate_sensor_cross_references(artifact_type_index)

            self._policy_index = policy_index
            self._rule_index = rule_index
            self._hierarchy = hierarchy
            self._artifact_type_index = artifact_type_index

            logger.info(
                "IntentRepository indexed %s policies, %s rules, "
                "and %s artifact types.",
                len(self._policy_index),
                len(self._rule_index),
                len(self._artifact_type_index),
            )

    # ID: e76e3d0e-b0c6-4b6a-bb9e-20a2bc8d5134
    def _validate_sensor_cross_references(
        self, artifact_type_index: dict[str, ArtifactTypeRef]
    ) -> None:
        """Cross-validate supported_sensors ↔ worker declarations (ADR-120 D3).

        Four predicates must hold:
          P1: every sensor named in artifact_type.supported_sensors has a
              worker declaration in .intent/workers/.
          P2: every such sensor's mandate.scope.artifact_type includes the
              type that lists it.
          P3: every sensing-class worker's declared artifact_type IDs are
              registered in the F-41 index.
          P4: every sensing-class worker appears in the supported_sensors
              list of each type it claims.

        Fails closed (raises GovernanceError) in strict mode; logs warnings
        in lenient mode. Worker declarations that cannot be loaded are
        skipped with a warning rather than failing the entire init.
        """
        # Load all worker declarations keyed by bare name (strip "workers/" prefix).
        worker_decls: dict[str, dict[str, Any]] = {}
        for worker_path_id in self.list_workers():
            bare = worker_path_id.split("/")[-1]
            try:
                worker_decls[bare] = self.load_worker(worker_path_id)
            except GovernanceError as exc:
                logger.warning(
                    "sensor cross-validation: could not load worker %s: %s",
                    worker_path_id,
                    exc,
                )

        errors: list[str] = []

        # P1 + P2: for each type's supported_sensors list.
        for type_ref in artifact_type_index.values():
            type_id = type_ref.id
            supported: list[str] = type_ref.content.get("supported_sensors") or []
            for sensor_name in supported:
                if sensor_name not in worker_decls:
                    errors.append(
                        f"[P1] artifact_type '{type_id}' lists sensor "
                        f"'{sensor_name}' in supported_sensors but no worker "
                        f"declaration exists for it"
                    )
                    continue
                declared_types: list[str] = (
                    worker_decls[sensor_name]
                    .get("mandate", {})
                    .get("scope", {})
                    .get("artifact_type")
                    or []
                )
                if type_id not in declared_types:
                    errors.append(
                        f"[P2] artifact_type '{type_id}' lists sensor "
                        f"'{sensor_name}' but that worker's "
                        f"mandate.scope.artifact_type does not include '{type_id}'"
                    )

        # P3 + P4: for each sensing-class worker.
        for bare_name, decl in worker_decls.items():
            identity = decl.get("identity") or {}
            if identity.get("class") != "sensing":
                continue
            declared_types = (
                decl.get("mandate", {}).get("scope", {}).get("artifact_type") or []
            )
            for type_id in declared_types:
                if type_id not in artifact_type_index:
                    errors.append(
                        f"[P3] sensor '{bare_name}' declares artifact_type "
                        f"'{type_id}' but no such artifact type is registered"
                    )
                    continue
                type_supported: list[str] = (
                    artifact_type_index[type_id].content.get("supported_sensors") or []
                )
                if bare_name not in type_supported:
                    errors.append(
                        f"[P4] sensor '{bare_name}' declares artifact_type "
                        f"'{type_id}' but artifact_type '{type_id}'.supported_sensors "
                        f"does not list '{bare_name}'"
                    )

        if not errors:
            return

        msg = (
            f"IntentRepository sensor cross-validation failed "
            f"({len(errors)} error(s)):\n" + "\n".join(f"  {e}" for e in errors)
        )
        if self._strict:
            raise GovernanceError(msg)
        logger.warning(msg)

    def _build_artifact_type_index(self) -> dict[str, ArtifactTypeRef]:
        """Walk .intent/artifact_types/ and load each declaration.

        Per ADR-090 D1, declarations live at .intent/artifact_types/<id>.yaml.
        Each declaration's top-level `id` field is the lookup key (NOT the
        filename — the filename is convention, the id is authority).

        Duplicate ids fail in strict mode; in lenient mode the second one is
        skipped with a warning.
        """
        artifact_types_dir = self._root / "artifact_types"
        index: dict[str, ArtifactTypeRef] = {}

        if not artifact_types_dir.exists():
            return index

        for path in self._iter_policy_files(artifact_types_dir):
            try:
                content = self.load_document(path)
            except GovernanceError as e:
                if self._strict:
                    raise
                logger.warning("Skipping unreadable artifact_type %s: %s", path, e)
                continue

            artifact_type_id = content.get("id")
            if not isinstance(artifact_type_id, str) or not artifact_type_id.strip():
                msg = (
                    f"artifact_type declaration missing 'id' field: {path}. "
                    f"Per ADR-090 D2, 'id' is required."
                )
                if self._strict:
                    raise GovernanceError(msg)
                logger.warning(msg)
                continue

            if artifact_type_id in index:
                msg = (
                    f"Duplicate artifact_type id: {artifact_type_id!r} "
                    f"({index[artifact_type_id].path} vs {path})"
                )
                if self._strict:
                    raise GovernanceError(msg)
                logger.warning(msg)
                continue

            index[artifact_type_id] = ArtifactTypeRef(
                id=artifact_type_id,
                path=path,
                content=content,
            )

        return index

    def _build_policy_index(self) -> tuple[dict[str, PolicyRef], dict[str, list[str]]]:
        search_roots = self._load_active_folders()

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
                        rule_content_hash=compute_rule_content_hash(content),
                    )

        return rule_index

    def _check_root_safety(self) -> None:
        if self._allow_writable_root:
            return

        try:
            writable = self._root.exists() and self._root.is_dir()
        except OSError:
            writable = False

        if writable:
            raise GovernanceError(
                f".intent root is writable but allow_writable_root=False: {self._root}"
            )

    def _load_active_folders(self) -> list[str]:
        tree_path = self._root / "META" / "intent_tree.yaml"

        if not tree_path.exists():
            logger.warning(
                "META/intent_tree.yaml not found at %s — falling back to minimal required set. "
                "This is a governance gap: intent_tree.yaml must declare the Mind structure.",
                tree_path,
            )
            return ["META", "constitution", "rules"]

        try:
            data = strict_yaml_processor.load_strict(tree_path)
            required = data.get("required_directories", [])
            optional = data.get("optional_directories", [])
            active = list(dict.fromkeys(required + optional))
            logger.debug(
                "Loaded %d active folders from META/intent_tree.yaml", len(active)
            )
            return active
        except Exception as e:
            logger.error(
                "Failed to load META/intent_tree.yaml: %s — falling back to minimal required set.",
                e,
            )
            return ["META", "constitution", "rules"]

    def _iter_policy_files(self, policies_dir: Path) -> Iterable[Path]:
        for suffix in ("*.yaml", "*.yml", "*.json"):
            yield from policies_dir.rglob(suffix)

    def _policy_id_from_path(self, path: Path) -> str:
        try:
            rel = path.relative_to(self._root)
            return str(rel.with_suffix("")).replace("\\", "/")
        except ValueError:
            return path.stem

    def _category_from_policy_id(self, policy_id: str) -> str:
        parts = policy_id.split("/")
        if len(parts) >= 2 and parts[0] in ("policies", "standards"):
            return parts[1]
        return "uncategorized"

    def _candidate_paths_for_id(self, policy_id: str) -> list[Path]:
        base = self.resolve_rel(policy_id)
        return [
            Path(str(base) + ".yaml"),
            Path(str(base) + ".yml"),
            Path(str(base) + ".json"),
        ]

    def _extract_rules(self, rules: Any) -> Iterable[tuple[str, dict[str, Any]]]:
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

    def _extract_rule_phase(self, rule: dict[str, Any]) -> str | None:
        phase = rule.get("phase")
        if isinstance(phase, str) and phase.strip():
            return phase.strip()

        applies_in = rule.get("applies_in")
        if isinstance(applies_in, str) and applies_in.strip():
            return applies_in.strip()

        phases = rule.get("phases")
        if isinstance(phases, list) and phases:
            first = phases[0]
            if isinstance(first, str) and first.strip():
                return first.strip()

        return None

    def _extract_rule_authority(self, rule: dict[str, Any]) -> str | None:
        authority = rule.get("authority")
        if isinstance(authority, str) and authority.strip():
            return authority.strip()

        owner = rule.get("owner")
        if isinstance(owner, str) and owner.strip():
            return owner.strip()

        return None


_INTENT_REPO: IntentRepository | None = None
_INTENT_REPO_LOCK = Lock()


# ID: 607b0d6e-c24a-4adb-899e-f15f2312fb0d
def get_intent_repository() -> IntentRepository:
    global _INTENT_REPO
    with _INTENT_REPO_LOCK:
        if _INTENT_REPO is None:
            _INTENT_REPO = IntentRepository(strict=True)
        return _INTENT_REPO
