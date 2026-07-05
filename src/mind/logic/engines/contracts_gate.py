# src/mind/logic/engines/contracts_gate.py

"""
Contracts gate — cross-cutting coherence checks on data contracts.

Dispatches four check_types today:

- layer_scope_coherence (#612, ADR-102): for every data_contract under
  .intent/enforcement/contracts/, check whether each governed_class's
  instantiation sites in src/ live exclusively in a layer whose
  constitutional rules forbid the operations the contract enforces.
  Static analysis; emits constitutional-incoherence findings.

- asymmetric_contract_findings (#613): when the same class is governed
  by multiple schema_conformance rules and one rule produces zero
  findings in a lookback window while another fires N>0, surface the
  high-firing rule's binding as suspect. The empirical counterpart to
  layer_scope_coherence — catches mis-scoped contracts via observed
  finding-count asymmetry against core.audit_findings.

- rule_binding_iceberg (#614): when a schema_conformance rule produces
  many findings against few distinct subjects (file_paths) over the
  lookback window, surface the rule's binding as suspect — the
  iceberg-shape signal (high finding count concentrated on a small
  source-file set) typically means the rule is mis-scoped to a class
  that consistently fails it, not that the class needs reshaping. Per
  memory feedback_iceberg_class_findings, the cluster pattern itself
  is the diagnostic. The canonical case (Finding.json firing 16
  findings against 2 files, ratio 8) is what triggered ADR-102; this
  rule catches that shape even when only one contract is involved.

- passive_gate_symbol_attestation (ADR-142): every Class A passive_gate
  mapping entry carries an enforced_by param that names the Python
  symbol responsible for enforcement. This check resolves each
  enforced_by dotted path to a source file under src/ and confirms the
  named symbol is defined there. Stale claims (symbol deleted, renamed,
  or moved) are blocking violations. Pure AST/filesystem — no DB access,
  no imports, no runtime execution.

The canonical case (Finding.json firing N>0 against AuditFinding while
AuditFinding.json fires 0) is what triggered ADR-102; the three rules
together catch the bind-error pattern from static, asymmetric, and
iceberg angles.

LAYER: mind.logic.engines — read-only verification. No file writes.
DB access (asymmetric / iceberg checks) is via the audit context's
injected session per architecture.boundary.database_session_access —
Mind layer does not open sessions itself.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import yaml
from sqlalchemy import text

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult, EvidenceClass


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


logger = getLogger(__name__)


_ENGINE_ID = "contracts_gate"
_RULE_ID_LAYER_SCOPE_COHERENCE = "data.contracts.layer_scope_coherence"
_RULE_ID_ASYMMETRIC_FINDINGS = "data.contracts.asymmetric_contract_findings"
_RULE_ID_RULE_BINDING_ICEBERG = "data.contracts.rule_binding_iceberg"
_RULE_ID_PASSIVE_GATE_ATTESTATION = "governance.passive_gate.enforced_by_must_resolve"

# Default lookback window for the DB-backed checks. 24h gives the daemon
# multiple audit cycles to populate counts without letting a single
# anomalous cycle dominate. Tunable per-mapping via `lookback_hours`.
_DEFAULT_ASYMMETRY_LOOKBACK_HOURS = 24

# Default thresholds for rule_binding_iceberg. min_findings + max_distinct
# files jointly define the iceberg shape: many findings concentrated on
# few source files. The canonical ADR-102 case (Finding.json fired 16
# findings on 2 files) fires under these defaults. Both tunable per
# mapping. Schema-conformance rules' check_ids match the suffix below.
_DEFAULT_ICEBERG_LOOKBACK_HOURS = 24
_DEFAULT_ICEBERG_MIN_FINDINGS = 10
_DEFAULT_ICEBERG_MAX_DISTINCT_FILES = 3
_SCHEMA_CONFORMANCE_RULE_PREFIX = "data.contracts."
_SCHEMA_CONFORMANCE_RULE_SUFFIX = "_conforms"

# Default severity for rule findings emitted by this engine. All three
# context-level rules in contracts_gate declare enforcement: reporting,
# which `rule_executor._map_enforcement_to_severity` maps to
# AuditSeverity.INFO. The executor overrides each finding's severity at
# dispatch time per ADR-098 D4; the value here is what callers see in
# direct (out-of-executor) invocations — e.g. unit tests, smoke checks.
# Keep aligned with the parent rules' enforcement so the two paths agree.
# The dispatch-error finding (verify_context's unsupported check_type
# fallback) keeps HIGH because it signals a config bug, not a rule fact.
_DEFAULT_FINDING_SEVERITY = AuditSeverity.INFO

# Constitutional layers under src/ where instantiation sites are meaningful
# for scope-coherence analysis. shared/ is intentionally excluded — it
# carries cross-layer infrastructure and is not itself a "layer" in the
# constitutional sense.
_LAYER_NAMES = frozenset({"mind", "body", "will", "api", "cli"})

# Fields whose presence in a contract's `required` set implies the
# contract enforces a persistence-attribution discipline that requires
# the governed class to cross a layer boundary the class's source layer
# may forbid. Initial seed: worker_uuid (blackboard FK). Future fields
# (e.g. proposals.claimed_by analogues) can join when they earn the same
# enforcement shape.
_PERSISTENCE_ATTRIBUTION_FIELDS = frozenset({"worker_uuid"})

# Layers whose constitutional rules forbid the operations
# persistence-attribution requires. A class living exclusively in a
# forbidding layer cannot satisfy contracts requiring those operations.
# Initial seed: Mind (architecture.mind.no_database_access /
# no_filesystem_writes).
_LAYERS_THAT_FORBID_PERSISTENCE = frozenset({"mind"})


# ID: 71959b3f-d82c-4bf2-b2bc-7a644e7bebb0
class ContractsGateEngine(BaseEngine):
    """Cross-cutting contract-coherence engine (#612, ADR-102).

    Consumes filesystem-resident data contracts and source files to
    evaluate scope-coherence invariants that depend on the cross-product
    of (contract requirements, governed class layer distribution) —
    not on any single file. Per-file dispatch is a contract violation;
    the rule mapping must scope this rule context-level.
    """

    engine_id = _ENGINE_ID
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict
    _context_check_types: ClassVar[frozenset[str]] = frozenset(
        {
            "layer_scope_coherence",
            "asymmetric_contract_findings",
            "rule_binding_iceberg",
            "passive_gate_symbol_attestation",
        }
    )

    # ID: 85fe18c4-fa47-4ba1-a8ac-5d7df73a17db
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        check_type = params.get("check_type", "<unknown>")
        return EngineResult(
            ok=False,
            message=f"contracts_gate.{check_type} is context-level only.",
            violations=[
                f"contracts_gate received per-file dispatch for check_type "
                f"'{check_type}'. Mapping must scope this rule context-level."
            ],
            engine_id=self.engine_id,
        )

    # ID: 7ee4d8b2-ba31-4d4c-9ae5-1be5fb266a2d
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        check_type = params.get("check_type")
        if check_type == "layer_scope_coherence":
            return _check_layer_scope_coherence(context)
        if check_type == "asymmetric_contract_findings":
            return await _check_asymmetric_contract_findings(context, params)
        if check_type == "rule_binding_iceberg":
            return await _check_rule_binding_iceberg(context, params)
        if check_type == "passive_gate_symbol_attestation":
            return _check_passive_gate_symbol_attestation(context, params)
        return [
            AuditFinding(
                check_id=f"{self.engine_id}.{check_type or 'missing'}.error",
                severity=AuditSeverity.HIGH,
                message=(
                    f"contracts_gate.verify_context received unsupported "
                    f"check_type '{check_type}'."
                ),
            )
        ]


# ID: 1f2f6bf4-8458-4814-93e3-65c323135ea1
def _check_layer_scope_coherence(context: AuditorContext) -> list[AuditFinding]:
    """Detect contracts binding layer-incoherent classes.

    Iterates .intent/enforcement/contracts/*.json. For each contract whose
    `required` set contains a persistence-attribution field (worker_uuid),
    walks the governed_classes list. For each governed class, determines
    the layer distribution of its instantiation sites under src/. If all
    sites live in a layer that forbids the operations persistence-attribution
    requires (Mind: no DB access), emits an AuditFinding flagging the
    binding as categorically incoherent.
    """
    findings: list[AuditFinding] = []
    repo_root: Path = context.paths.repo_root
    contracts_dir = repo_root / ".intent" / "enforcement" / "contracts"
    src_root = repo_root / "src"

    if not contracts_dir.is_dir():
        logger.warning("contracts_gate: contracts directory missing: %s", contracts_dir)
        return findings

    classes_of_interest: set[str] = set()
    contract_data: dict[Path, dict[str, Any]] = {}
    for contract_path in sorted(contracts_dir.glob("*.json")):
        try:
            data = json.loads(contract_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "contracts_gate: skipping malformed %s: %s", contract_path, e
            )
            continue
        required = set(data.get("required") or [])
        if not (required & _PERSISTENCE_ATTRIBUTION_FIELDS):
            continue
        governed = data.get("governed_classes") or []
        if not governed:
            continue
        contract_data[contract_path] = data
        classes_of_interest.update(governed)

    if not classes_of_interest:
        return findings

    instantiation_layers = _index_instantiation_layers(classes_of_interest, src_root)

    for contract_path, data in contract_data.items():
        contract_id = (data.get("metadata") or {}).get("id", contract_path.stem)
        required = set(data.get("required") or [])
        attribution_fields = sorted(required & _PERSISTENCE_ATTRIBUTION_FIELDS)
        for class_name in data.get("governed_classes") or []:
            layers = instantiation_layers.get(class_name, set())
            if not layers:
                continue
            if not layers.issubset(_LAYERS_THAT_FORBID_PERSISTENCE):
                continue
            layers_str = ", ".join(sorted(layers))
            attribution_str = ", ".join(attribution_fields)
            findings.append(
                AuditFinding(
                    check_id=_RULE_ID_LAYER_SCOPE_COHERENCE,
                    severity=_DEFAULT_FINDING_SEVERITY,
                    message=(
                        f"Contract {contract_path.name} (id: {contract_id}) binds "
                        f"class '{class_name}' whose instantiation sites are exclusively "
                        f"in src/{layers_str}/ — a layer constitutionally forbidden from "
                        f"DB access. The contract requires persistence-attribution field(s) "
                        f"[{attribution_str}] that cannot be satisfied by a class confined "
                        f"to this layer. Binding is categorically incoherent — retire the "
                        f"contract or remove {class_name} from governed_classes. "
                        f"See ADR-102 for the canonical case (Finding.json + AuditFinding)."
                    ),
                    file_path=str(contract_path.relative_to(repo_root)),
                    context={
                        "contract_id": contract_id,
                        "class_name": class_name,
                        "instantiation_layers": sorted(layers),
                        "required_attribution_fields": attribution_fields,
                    },
                )
            )
    return findings


_CLASS_CALL_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\(")


# ID: bf7c2602-441b-47bd-97b9-ab8e4e466a5d
def _index_instantiation_layers(
    classes: set[str], src_root: Path
) -> dict[str, set[str]]:
    """Single-pass src/ walk; returns {ClassName: {layer, layer, ...}}.

    A class's own definition line (`class ClassName(...)`) is intentionally
    NOT counted as an instantiation site — it tells us where the class
    LIVES, not where it's USED. Walks .py files only.
    """
    layers_by_class: dict[str, set[str]] = {c: set() for c in classes}
    if not src_root.is_dir():
        return layers_by_class

    class_def_pattern = re.compile(r"\bclass\s+$")
    for py_file in src_root.rglob("*.py"):
        try:
            rel = py_file.relative_to(src_root)
        except ValueError:
            continue
        if not rel.parts:
            continue
        layer = rel.parts[0]
        if layer not in _LAYER_NAMES:
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not any(c in content for c in classes):
            continue
        for match in _CLASS_CALL_PATTERN.finditer(content):
            name = match.group(1)
            if name not in classes:
                continue
            start = max(0, match.start() - 30)
            prefix = content[start : match.start()]
            if class_def_pattern.search(prefix):
                continue
            layers_by_class[name].add(layer)

    return layers_by_class


# ID: d9accb7b-dc2e-4fde-af86-c9e8a9554998
async def _check_asymmetric_contract_findings(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    """Detect classes governed by multiple rules with asymmetric finding counts.

    Reads enforcement mappings to enumerate rules whose engine is
    ast_gate with check_type schema_conformance, resolves each rule's
    schema_ref to its contract, and builds class → {rule_ids} from the
    contracts' governed_classes. For classes appearing under ≥2 rules,
    queries core.audit_findings for finding counts per rule within the
    lookback window. If at least one rule fires zero and at least one
    fires N>0 on the same class, the high-firing rule's binding is
    suspect — emit a meta-finding pointing at it.

    The canonical case this rule generalizes (the literal trigger for
    ADR-102): Finding.json firing 9 against AuditFinding while
    AuditFinding.json fires 0 → asymmetry → Finding.json's binding was
    the bug, not AuditFinding's shape.

    Skip-silently semantics on missing infrastructure: no mappings
    file → empty findings; no multi-rule classes → empty findings; no
    db_session injected → empty findings (check deferred to next cycle
    where the session is available).
    """
    findings: list[AuditFinding] = []
    repo_root: Path = context.paths.repo_root
    mappings_path = (
        repo_root / ".intent" / "enforcement" / "mappings" / "data" / "governance.yaml"
    )
    contracts_dir = repo_root / ".intent" / "enforcement" / "contracts"

    if not mappings_path.exists():
        logger.warning("contracts_gate: mappings not found: %s", mappings_path)
        return findings

    try:
        mappings_doc = yaml.safe_load(mappings_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        logger.warning("contracts_gate: malformed mappings: %s", e)
        return findings

    rule_to_schema: dict[str, str] = {}
    for rule_id, mapping in (mappings_doc.get("mappings") or {}).items():
        if not isinstance(mapping, dict):
            continue
        engine = mapping.get("engine")
        params_block = mapping.get("params") or {}
        if engine != "ast_gate":
            continue
        if params_block.get("check_type") != "schema_conformance":
            continue
        schema_ref = params_block.get("schema_ref")
        if isinstance(schema_ref, str) and schema_ref:
            rule_to_schema[rule_id] = schema_ref

    if not rule_to_schema:
        return findings

    schema_to_classes: dict[str, set[str]] = {}
    for schema_ref in set(rule_to_schema.values()):
        contract_path = contracts_dir / f"{schema_ref}.json"
        if not contract_path.exists():
            continue
        try:
            data = json.loads(contract_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        governed = set(data.get("governed_classes") or [])
        if governed:
            schema_to_classes[schema_ref] = governed

    class_to_rules: dict[str, set[str]] = {}
    for rule_id, schema_ref in rule_to_schema.items():
        for cls in schema_to_classes.get(schema_ref, set()):
            class_to_rules.setdefault(cls, set()).add(rule_id)

    multi_rule_classes = {c: r for c, r in class_to_rules.items() if len(r) >= 2}
    if not multi_rule_classes:
        return findings

    session = getattr(context, "db_session", None)
    if session is None:
        logger.debug(
            "contracts_gate.asymmetric_contract_findings: db_session not "
            "injected — check deferred to next audit cycle."
        )
        return findings

    lookback_hours = int(
        params.get("lookback_hours", _DEFAULT_ASYMMETRY_LOOKBACK_HOURS)
    )
    rule_ids_of_interest = sorted(
        {rid for rules in multi_rule_classes.values() for rid in rules}
    )

    count_query = text(
        """
        SELECT check_id, COUNT(*) AS finding_count
        FROM core.audit_findings
        WHERE check_id = ANY(:rule_ids)
          AND created_at > now() - make_interval(hours => :lookback_hours)
        GROUP BY check_id
        """
    )
    result = await session.execute(
        count_query,
        {"rule_ids": rule_ids_of_interest, "lookback_hours": lookback_hours},
    )
    rule_counts: dict[str, int] = {
        row.check_id: int(row.finding_count) for row in result
    }
    for rid in rule_ids_of_interest:
        rule_counts.setdefault(rid, 0)

    for cls, rule_set in sorted(multi_rule_classes.items()):
        counts = {rid: rule_counts[rid] for rid in sorted(rule_set)}
        zero_rules = sorted(rid for rid, c in counts.items() if c == 0)
        firing_rules = sorted(
            ((rid, c) for rid, c in counts.items() if c > 0), key=lambda pair: pair[0]
        )
        if not zero_rules or not firing_rules:
            continue
        firing_str = ", ".join(f"{rid}(N={c})" for rid, c in firing_rules)
        zero_str = ", ".join(zero_rules)
        findings.append(
            AuditFinding(
                check_id=_RULE_ID_ASYMMETRIC_FINDINGS,
                severity=_DEFAULT_FINDING_SEVERITY,
                message=(
                    f"Class '{cls}' is governed by multiple schema_conformance rules "
                    f"with asymmetric finding counts over the last {lookback_hours}h: "
                    f"firing [{firing_str}], silent [{zero_str}]. The silent rule(s)' "
                    f"contract(s) conform; the firing rule(s)' binding is suspect — "
                    f"verify against the class's operational role rather than "
                    f"reshaping the class. Canonical case: ADR-102 (Finding.json fired "
                    f"N>0 against AuditFinding while AuditFinding.json fired 0; the "
                    f"binding error was Finding.json's, not AuditFinding's shape)."
                ),
                context={
                    "class_name": cls,
                    "rule_counts": counts,
                    "zero_rules": zero_rules,
                    "firing_rules": [rid for rid, _ in firing_rules],
                    "lookback_hours": lookback_hours,
                },
            )
        )
    return findings


# ID: 556abbec-b698-4d74-b07a-30faaeb5f31a
async def _check_rule_binding_iceberg(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    """Detect schema_conformance rules whose findings cluster as icebergs.

    Queries core.audit_findings for findings whose check_id matches the
    schema_conformance namespace (data.contracts.*_conforms) within the
    lookback window. Groups by check_id; counts findings and distinct
    file_paths per rule. When a rule's finding count exceeds
    min_findings AND its distinct-file count is at or below
    max_distinct_files, the cluster shape (many findings on few files)
    signals the rule's binding is suspect — investigate the rule's
    scope rather than the classes.

    Complements asymmetric_contract_findings (#613): the asymmetric
    check fires when multiple rules govern the same class; this iceberg
    check fires even with one rule, when that rule keeps firing on the
    same small file set across cycles.

    Skip-silently when db_session is not injected (consistent with the
    runtime_gate pattern). The canonical ADR-102 case (Finding.json
    firing 16 findings on 2 files) fires under default thresholds.
    """
    findings: list[AuditFinding] = []

    session = getattr(context, "db_session", None)
    if session is None:
        logger.debug(
            "contracts_gate.rule_binding_iceberg: db_session not injected — "
            "check deferred to next audit cycle."
        )
        return findings

    lookback_hours = int(params.get("lookback_hours", _DEFAULT_ICEBERG_LOOKBACK_HOURS))
    min_findings = int(params.get("min_findings", _DEFAULT_ICEBERG_MIN_FINDINGS))
    max_distinct_files = int(
        params.get("max_distinct_files", _DEFAULT_ICEBERG_MAX_DISTINCT_FILES)
    )
    rule_prefix = _SCHEMA_CONFORMANCE_RULE_PREFIX
    rule_suffix = _SCHEMA_CONFORMANCE_RULE_SUFFIX

    iceberg_query = text(
        """
        SELECT
            check_id,
            COUNT(*) AS finding_count,
            COUNT(DISTINCT file_path) AS distinct_files,
            ARRAY_AGG(DISTINCT file_path ORDER BY file_path) AS file_paths
        FROM core.audit_findings
        WHERE check_id LIKE :rule_prefix || '%' || :rule_suffix
          AND created_at > now() - make_interval(hours => :lookback_hours)
          AND file_path IS NOT NULL
        GROUP BY check_id
        HAVING COUNT(*) >= :min_findings
           AND COUNT(DISTINCT file_path) <= :max_distinct_files
        ORDER BY check_id
        """
    )
    result = await session.execute(
        iceberg_query,
        {
            "rule_prefix": rule_prefix,
            "rule_suffix": rule_suffix,
            "lookback_hours": lookback_hours,
            "min_findings": min_findings,
            "max_distinct_files": max_distinct_files,
        },
    )

    for row in result:
        finding_count = int(row.finding_count)
        distinct_files = int(row.distinct_files)
        file_paths = list(row.file_paths or [])
        ratio = finding_count / distinct_files if distinct_files else 0.0
        files_str = ", ".join(file_paths) if file_paths else "<no file_path>"
        findings.append(
            AuditFinding(
                check_id=_RULE_ID_RULE_BINDING_ICEBERG,
                severity=_DEFAULT_FINDING_SEVERITY,
                message=(
                    f"Rule '{row.check_id}' shows iceberg-shaped finding cluster "
                    f"over the last {lookback_hours}h: {finding_count} findings "
                    f"concentrated on {distinct_files} distinct file(s) "
                    f"(ratio {ratio:.1f}). Files: [{files_str}]. The cluster "
                    f"shape signals the rule's binding is suspect — investigate "
                    f"whether the rule's governed_classes correctly correspond to "
                    f"the operational role of the affected classes, rather than "
                    f"treating the findings as drift to be cleared. Canonical "
                    f"case: ADR-102 (Finding.json fired 16 findings on 2 files; "
                    f"the binding was the bug, not the classes' shapes)."
                ),
                context={
                    "rule_id": row.check_id,
                    "finding_count": finding_count,
                    "distinct_files": distinct_files,
                    "ratio": round(ratio, 2),
                    "file_paths": file_paths,
                    "lookback_hours": lookback_hours,
                    "thresholds": {
                        "min_findings": min_findings,
                        "max_distinct_files": max_distinct_files,
                    },
                },
            )
        )
    return findings


# ID: f1fa9edf-8dc6-4a6b-8553-369810216e44
def _check_passive_gate_symbol_attestation(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    """Verify every Class A passive_gate enforced_by path resolves to a live symbol.

    Walks all .intent/enforcement/mappings/**/*.yaml. For each entry with
    engine: passive_gate and attestation_class: 'A', extracts the enforced_by
    dotted path, resolves it to a source file under src/, and confirms the
    named class or function exists via AST. Stale claims are blocking violations
    (ADR-142 D2).

    Resolution algorithm:
    - Strip trailing documentation suffixes (e.g. ' enum').
    - Split on '.'; progressively lengthen the file-path prefix until a .py file
      (or package __init__.py) matches under src/.
    - The first remaining element after the matched prefix is the symbol name;
      subsequent elements (method names) are not verified — class/function
      existence is sufficient.
    - Emit a CRITICAL finding for any enforced_by that fails to resolve.
    """
    findings: list[AuditFinding] = []
    repo_root: Path = context.paths.repo_root
    mappings_root_param = params.get("mappings_root", ".intent/enforcement/mappings")
    src_root_param = params.get("src_root", "src")
    mappings_root = repo_root / mappings_root_param
    src_root = repo_root / src_root_param

    if not mappings_root.is_dir():
        logger.warning(
            "contracts_gate.passive_gate_symbol_attestation: mappings root missing: %s",
            mappings_root,
        )
        return findings

    for yaml_file in sorted(mappings_root.rglob("*.yaml")):
        try:
            content = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as e:
            logger.warning(
                "contracts_gate: skipping malformed %s: %s", yaml_file.name, e
            )
            continue

        if not isinstance(content, dict):
            continue
        mappings_block = content.get("mappings") or {}
        for rule_id, mapping in mappings_block.items():
            if not isinstance(mapping, dict):
                continue
            if mapping.get("engine") != "passive_gate":
                continue
            entry_params = mapping.get("params") or {}
            if entry_params.get("attestation_class") != "A":
                continue
            enforced_by = (entry_params.get("enforced_by") or "").strip()
            if not enforced_by:
                continue

            # Strip trailing documentation suffixes like " enum"
            enforced_by_clean = enforced_by.split(" ")[0]

            resolved = _resolve_enforced_by_symbol(enforced_by_clean, src_root)
            if resolved is None:
                rel_yaml = str(yaml_file.relative_to(repo_root))
                findings.append(
                    AuditFinding(
                        check_id=_RULE_ID_PASSIVE_GATE_ATTESTATION,
                        severity=AuditSeverity.BLOCK,
                        message=(
                            f"passive_gate rule '{rule_id}' in {rel_yaml} declares "
                            f"enforced_by='{enforced_by}' but no matching Python "
                            f"symbol was found under src/. The governance claim is "
                            f"silently false — audit returns ok=True on an "
                            f"enforcement that no longer exists. Resolve by: "
                            f"(1) updating enforced_by to the symbol's current "
                            f"dotted path, or (2) reclassifying this rule to the "
                            f"correct attestation_class if enforcement moved to a "
                            f"different mechanism."
                        ),
                        file_path=rel_yaml,
                        context={
                            "rule_id": rule_id,
                            "enforced_by": enforced_by,
                            "mappings_file": rel_yaml,
                        },
                    )
                )
            else:
                logger.debug(
                    "contracts_gate: %s enforced_by '%s' resolved to %s",
                    rule_id,
                    enforced_by,
                    resolved,
                )

    return findings


# ID: 3828ee62-edbe-452a-bf0b-33d75edeb6b6
def _resolve_enforced_by_symbol(dotted_path: str, src_root: Path) -> str | None:
    """Resolve a dotted Python path to a (file_path, symbol_name) pair.

    Returns a short description string on success, None on failure. The
    caller treats None as a stale claim.

    Strategy: split the dotted path into parts; try progressively longer
    prefixes as the filesystem path under src_root until a .py file matches.
    The first unmatched part is the symbol name. Confirms the symbol exists
    in the file's AST (class or function definition at module level or nested
    one level deep — sufficient for the enforcement patterns in use).
    """
    parts = dotted_path.split(".")
    if len(parts) < 2:
        return None

    for boundary in range(1, len(parts)):
        candidate_path = src_root / Path(*parts[:boundary]).with_suffix(".py")
        init_path = src_root / Path(*parts[:boundary]) / "__init__.py"
        symbol_idx = boundary

        matched: Path | None = None
        if candidate_path.is_file():
            matched = candidate_path
        elif init_path.is_file():
            matched = init_path

        if matched is None:
            continue
        if symbol_idx >= len(parts):
            return None

        symbol_name = parts[symbol_idx]
        if _symbol_defined_in_file(symbol_name, matched):
            return f"{matched}::{symbol_name}"

    return None


# ID: bc5675d9-d36d-4438-bc06-935940e16846
def _symbol_defined_in_file(symbol_name: str, file_path: Path) -> bool:
    """Return True if symbol_name is defined as a class or function in file_path.

    Checks module-level and one level of nesting (methods inside classes).
    Uses AST parse — no imports, no runtime execution.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == symbol_name:
                return True
    return False
