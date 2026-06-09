# src/mind/logic/engines/contracts_gate.py

"""
Contracts gate — cross-cutting layer-coherence checks on data contracts.

Dispatches one check_type today:

- layer_scope_coherence (#612, ADR-102): for every data_contract under
  .intent/enforcement/contracts/, check whether each governed_class's
  instantiation sites in src/ live exclusively in a layer whose
  constitutional rules forbid the operations the contract enforces.
  If so, emit a constitutional-incoherence finding.

  The canonical case this rule prevents: Finding.json bound CheckResult
  and AuditFinding to a 5-field nucleus including worker_uuid (which
  requires blackboard attribution via FK). AuditFinding lives exclusively
  in src/mind/; Mind is forbidden from DB access; therefore the binding
  was categorically incoherent. ADR-102 retired Finding.json; this rule
  prevents a recurrence.

LAYER: mind.logic.engines — read-only verification. No file writes, no
DB access (operates on filesystem-resident contracts + source AST scan).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


logger = getLogger(__name__)


_ENGINE_ID = "contracts_gate"
_CONTEXT_CHECK_TYPES = frozenset({"layer_scope_coherence"})
_RULE_ID_LAYER_SCOPE_COHERENCE = "data.contracts.layer_scope_coherence"

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

    @classmethod
    # ID: effd788b-b7b5-4d1e-ab2a-24d8d829e2f7
    def is_context_level_for(cls, check_type: str | None) -> bool:
        return check_type in _CONTEXT_CHECK_TYPES

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
                    severity=AuditSeverity.HIGH,
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
