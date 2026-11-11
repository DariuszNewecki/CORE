# src/mind/logic/record_contract.py

"""
The record contract (ADR-173): rules judge a resolved record, not a file.

A record is a mapping the caller has already resolved (D12): one version per
item on one date, version pins applied, every item checked against its type
schema. CORE judges it against rules and returns a ``RecordVerdict``:

- one ``RulePart`` per rule (D5), each with its own engine, evidence class,
  result and findings; a finding always names its rule;
- the outcome and evidence class aggregated from the parts (D2);
- ``record_sha256``, the SHA-256 of the record in its RFC 8785 (JCS)
  canonical form, scope included (D4). The evidence class says how CORE
  reached the verdict on these facts; it does not vouch that the record is
  true.

Mind layer: pure, no I/O. The engine lookup is injected; by default it is the
``EngineRegistry``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any, Literal

from shared.logger import getLogger
from shared.models.audit_models import EvidenceClass


logger = getLogger(__name__)

Result = Literal["pass", "fail", "undecided"]

# Strength order of evidence classes (ADR-113): proven > judged > attested.
_STRENGTH = {
    EvidenceClass.ATTESTED: 0,
    EvidenceClass.JUDGED: 1,
    EvidenceClass.PROVEN: 2,
}


def _strength(evidence: EvidenceClass) -> int:
    return _STRENGTH[evidence]


# engine_id of a part built from carried findings whose rule is not in the
# rule set (D12): no engine produced them.
CARRIED_ENGINE_ID = "carried"


@dataclass(frozen=True)
# ID: 6928fba1-70ef-4bcc-9d3f-33acd9fc7759
class RecordFinding:
    """One finding inside a part. ``item`` is an item id, or None for a
    finding about the record as a whole. ``carried`` marks a finding the
    caller supplied (load_findings / pre_findings), which CORE did not
    establish."""

    rule: str
    message: str
    blocking: bool
    item: str | None = None
    carried: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
# ID: 6f54b6b1-3eed-4a79-b081-785f3f3ed0ad
class RulePart:
    """The verdict of one rule (ADR-173 D5)."""

    rule_id: str
    engine_id: str
    evidence_class: EvidenceClass
    result: Result
    findings: tuple[RecordFinding, ...] = ()


@dataclass(frozen=True)
# ID: 390f17f9-b370-408f-85a8-c4c91fe20d86
class RecordVerdict:
    """The verdict on a record: aggregated outcome and class, the record's
    hash, and one part per rule. There is no verdict-level engine id (D5)."""

    outcome: Result
    evidence_class: EvidenceClass
    record_sha256: str
    parts: tuple[RulePart, ...]

    @property
    # ID: 0493cc21-b588-461e-906b-ff7955b0e463
    def rule_ids(self) -> tuple[str, ...]:
        """The rules behind this verdict, in part order."""
        return tuple(part.rule_id for part in self.parts)


@dataclass(frozen=True)
# ID: 79e1c107-c301-4680-8ae7-52367eaccf6e
class RecordRule:
    """A rule as the evaluator receives it (ADR-173 D9: from a catalog
    requirement; in memory until catalogs are loaded for records).
    ``blocking`` is the requirement's enforcement: a non-blocking rule's
    findings never fail the record."""

    rule_id: str
    engine: str
    params: Mapping[str, Any] = field(default_factory=dict)
    blocking: bool = True


# ---------------------------------------------------------------------------
# Per-rule result, scope and aggregation
# ---------------------------------------------------------------------------


# ID: c88f725e-3717-4c85-91a4-5d1a96736cd2
def part_result(findings: Iterable[RecordFinding]) -> Result:
    """D13: any blocking finding gives fail; only non-blocking findings give
    undecided; none gives pass."""
    findings = list(findings)
    if any(f.blocking for f in findings):
        return "fail"
    if findings:
        return "undecided"
    return "pass"


# ID: 8c98373b-da02-4ca6-b0a6-47801a953252
def record_scope(record: Mapping[str, Any]) -> frozenset[str] | None:
    """D7: the record's ``scope`` key, as a set of item ids, or None (judge
    everything)."""
    scope = record.get("scope")
    if scope is None:
        return None
    return frozenset(str(item) for item in scope)


# ID: b7fa85d8-7e66-40fe-8f8c-7748e98f50d8
def in_scope(finding: RecordFinding, scope: frozenset[str] | None) -> bool:
    """D13: with a scope, only findings on items in it count. A finding on
    the record as a whole (no item) always counts."""
    return scope is None or finding.item is None or finding.item in scope


# ID: 1391292c-d09e-4a8b-9b3f-02c6ce637fe4
def aggregate(
    parts: Iterable[RulePart], *, has_rules: bool = True
) -> tuple[Result, EvidenceClass]:
    """D2 and D8: the record's outcome and evidence class from its parts.

    fail if any part fails, with the strongest class among the failing parts
    (one proven failure proves the fail); else undecided if any part is
    undecided, or if there are no rules (D8); else pass. Outside a fail the
    class is the weakest among all parts, ATTESTED when there are none.
    """
    parts = list(parts)
    failing = [p for p in parts if p.result == "fail"]
    if failing:
        return "fail", max((p.evidence_class for p in failing), key=_strength)
    weakest = min(
        (p.evidence_class for p in parts),
        key=_strength,
        default=EvidenceClass.ATTESTED,
    )
    if not has_rules or any(p.result == "undecided" for p in parts):
        return "undecided", weakest
    return "pass", weakest


# ID: a7623361-5bd5-45f3-9a74-0c0f1574826f
def engine_part(engine: Any, rule: str, findings: Iterable[RecordFinding]) -> RulePart:
    """The part an engine returns from ``evaluate_record``."""
    findings = tuple(findings)
    return RulePart(
        rule_id=rule,
        engine_id=getattr(engine, "engine_id", type(engine).__name__),
        evidence_class=type(engine).evidence_class,
        result=part_result(findings),
        findings=findings,
    )


# ID: b47d0c78-6ddb-4ff5-a0df-45624c42a178
def record_items(
    record: Mapping[str, Any], item_types: Iterable[str] | None = None
) -> list[tuple[str, Mapping[str, Any]]]:
    """The record's items as (id, item), in id order, optionally only those
    whose ``type`` is in ``item_types`` (item kinds are rule parameters,
    ADR-173 D14). Out-of-scope items are included: the scope filters
    findings, not what a rule may read (D7)."""
    wanted = None if item_types is None else set(item_types)
    items = record.get("items") or {}
    return [
        (str(item_id), item)
        for item_id, item in sorted(items.items(), key=lambda kv: str(kv[0]))
        if isinstance(item, Mapping) and (wanted is None or item.get("type") in wanted)
    ]


# ---------------------------------------------------------------------------
# RFC 8785 (JCS) canonical form
# ---------------------------------------------------------------------------


def _jcs_number(value: float) -> str:
    """ECMAScript Number-to-String for a finite double (RFC 8785 3.2.2.3)."""
    if not math.isfinite(value):
        raise ValueError(f"JCS cannot represent {value!r}")
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    # repr is the shortest round-trip form; as a Decimal it gives digits d
    # and exponent such that |value| = 0.d x 10^n.
    _, digit_tuple, exponent = Decimal(repr(abs(value))).as_tuple()
    digits = "".join(map(str, digit_tuple)).lstrip("0")
    n = (
        len("".join(map(str, digit_tuple)))
        + int(exponent)
        - (len(digit_tuple) - len(digits))
    )
    digits = digits.rstrip("0")
    k = len(digits)
    if k <= n <= 21:
        text = digits + "0" * (n - k)
    elif 0 < n <= 21:
        text = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        text = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        exp_text = ("+" if e >= 0 else "-") + str(abs(e))
        text = (
            digits + "e" + exp_text
            if k == 1
            else (digits[0] + "." + digits[1:] + "e" + exp_text)
        )
    return sign + text


_ESCAPES = {
    '"': '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _jcs_string(value: str) -> str:
    out = []
    for ch in value:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


# ID: 90a11ab2-d395-448e-a0f3-27cd70a2cc1c
def canonical_json(value: Any) -> str:
    """The RFC 8785 (JCS) canonical JSON text of ``value``: no whitespace,
    object keys sorted by UTF-16 code units, ECMAScript number form. Written
    here so the contract needs no new dependency (ADR-173 D4)."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _jcs_number(value)
    if isinstance(value, str):
        return _jcs_string(value)
    if isinstance(value, Mapping):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"JCS object keys must be strings, got {key!r}")
        keys = sorted(value, key=lambda k: k.encode("utf-16-be"))
        return (
            "{"
            + ",".join(_jcs_string(k) + ":" + canonical_json(value[k]) for k in keys)
            + "}"
        )
    if isinstance(value, list | tuple):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    raise TypeError(f"JCS cannot represent {type(value).__name__}")


# ID: ac018d3c-d512-4470-b463-7e3b03d9f2f1
def record_sha256(record: Mapping[str, Any]) -> str:
    """D4: SHA-256 (hex) of the record's JCS form; the scope is part of the
    record, so it is part of the hash."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _carried(record: Mapping[str, Any]) -> list[RecordFinding]:
    """D12: the caller's load_findings and pre_findings, as findings."""
    carried: list[RecordFinding] = []
    for key, default_rule in (("load_findings", "load"), ("pre_findings", "pre")):
        for entry in record.get(key) or ():
            item = entry.get("item")
            carried.append(
                RecordFinding(
                    rule=str(entry.get("rule") or default_rule),
                    message=str(entry.get("message", "")),
                    blocking=bool(entry.get("blocking", True)),
                    item=None if item is None else str(item),
                    carried=True,
                )
            )
    return carried


def _default_engine_lookup(engine_id: str) -> Any:
    from mind.logic.engines.registry import EngineRegistry

    return EngineRegistry.get(engine_id)


def _missing_part(rule: RecordRule, message: str) -> RulePart:
    """D1: a rule whose engine is unknown or cannot judge records. BLOCK,
    like the engine-missing finding of a file audit; ATTESTED because no
    method established anything."""
    finding = RecordFinding(
        rule=rule.rule_id,
        message=message,
        blocking=True,
        details={"finding_type": "engine_missing"},
    )
    return RulePart(
        rule.rule_id, rule.engine, EvidenceClass.ATTESTED, "fail", (finding,)
    )


async def _rule_part(
    record: Mapping[str, Any],
    rule: RecordRule,
    lookup: Callable[[str], Any],
) -> RulePart:
    try:
        engine = lookup(rule.engine)
    except ValueError as exc:
        return _missing_part(rule, f"{rule.rule_id}.engine_missing: {exc}")
    if not getattr(engine, "supports_records", False):
        return _missing_part(
            rule,
            f"{rule.rule_id}.engine_missing: engine {rule.engine!r} cannot "
            "judge records (supports_records is False)",
        )
    try:
        produced = await engine.evaluate_record(record, rule.rule_id, dict(rule.params))
    except Exception as exc:  # an engine crash is never a pass (ADR-113 D3)
        logger.warning(
            "Record engine %s crashed on %s: %s", rule.engine, rule.rule_id, exc
        )
        finding = RecordFinding(
            rule=rule.rule_id,
            message=f"{rule.rule_id}.enforcement_failure: {exc}",
            blocking=True,
            details={"finding_type": "enforcement_failure"},
        )
        return RulePart(
            rule.rule_id, rule.engine, EvidenceClass.ATTESTED, "fail", (finding,)
        )
    findings = tuple(
        replace(f, rule=rule.rule_id, blocking=f.blocking and rule.blocking)
        for f in produced.findings
    )
    # The class is the engine's declaration (ADR-113 D2), never the part's own claim.
    return RulePart(
        rule_id=rule.rule_id,
        engine_id=getattr(engine, "engine_id", rule.engine),
        evidence_class=type(engine).evidence_class,
        result=part_result(findings),
        findings=findings,
    )


def _settle(
    part: RulePart, carried: list[RecordFinding], scope: frozenset[str] | None
) -> RulePart:
    """Add the carried findings for this rule, apply the scope, recompute the
    result. A part that holds a carried finding is ATTESTED: its result rests
    on facts CORE did not establish (D12)."""
    findings = [f for f in (*part.findings, *carried) if in_scope(f, scope)]
    evidence = part.evidence_class
    if any(f.carried for f in findings):
        evidence = EvidenceClass.ATTESTED
    return replace(
        part,
        evidence_class=evidence,
        result=part_result(findings),
        findings=tuple(findings),
    )


# ID: 0a6f4e8e-3879-481e-bb90-784b0629a54a
async def evaluate(
    record: Mapping[str, Any],
    rules: Iterable[RecordRule],
    *,
    engine_lookup: Callable[[str], Any] | None = None,
) -> RecordVerdict:
    """Judge ``record`` against ``rules`` (ADR-173). Async (D6).

    Each rule's engine runs ``evaluate_record``; carried caller findings are
    added under the rule they name, or as their own part when that rule is
    not in the set (D12); the scope filters findings (D7, D13); the parts
    aggregate per D2, and an empty rule set gives undecided (D8).
    """
    rules = list(rules)
    lookup = engine_lookup or _default_engine_lookup
    scope = record_scope(record)
    carried = _carried(record)
    rule_ids = {rule.rule_id for rule in rules}

    parts: list[RulePart] = []
    for rule in rules:
        part = await _rule_part(record, rule, lookup)
        mine = [f for f in carried if f.rule == rule.rule_id]
        parts.append(_settle(part, mine, scope))

    # D12: carried findings for a rule outside the set keep their own part.
    orphan_rules: dict[str, list[RecordFinding]] = {}
    for finding in carried:
        if finding.rule not in rule_ids:
            orphan_rules.setdefault(finding.rule, []).append(finding)
    for rule_id, findings in orphan_rules.items():
        kept = tuple(f for f in findings if in_scope(f, scope))
        parts.append(
            RulePart(
                rule_id,
                CARRIED_ENGINE_ID,
                EvidenceClass.ATTESTED,
                part_result(kept),
                kept,
            )
        )

    outcome, evidence = aggregate(parts, has_rules=bool(rules))
    return RecordVerdict(
        outcome=outcome,
        evidence_class=evidence,
        record_sha256=record_sha256(record),
        parts=tuple(parts),
    )


# Re-exported for engines that build parts.
__all__ = [
    "CARRIED_ENGINE_ID",
    "RecordFinding",
    "RecordRule",
    "RecordVerdict",
    "RulePart",
    "aggregate",
    "canonical_json",
    "engine_part",
    "evaluate",
    "in_scope",
    "part_result",
    "record_items",
    "record_scope",
    "record_sha256",
]
