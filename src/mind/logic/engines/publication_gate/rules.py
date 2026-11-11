# src/mind/logic/engines/publication_gate/rules.py

"""
The 10 publication rules (ADR-173 D14), as pure functions over a resolved
record (format ``library-snapshot/1``).

Each rule takes the record, the rule id and the rule's params from the
catalog, and returns findings; the evaluator turns them into pass / fail /
undecided (D13). Item kinds, type names and relation names come from params,
never from code. A ref whose target is not in the snapshot is reported only by
``reference``; every other rule skips it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from mind.logic.record_contract import RecordFinding


Item = Mapping[str, Any]
RuleFn = Callable[[Mapping[str, Any], str, Mapping[str, Any]], list[RecordFinding]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _items(record: Mapping[str, Any]) -> list[tuple[str, Item]]:
    items = record.get("items") or {}
    return [(str(k), v) for k, v in sorted(items.items(), key=lambda kv: str(kv[0]))]


def _refs(item: Item, rels: Iterable[str] | None = None) -> list[Mapping[str, Any]]:
    wanted = None if rels is None else set(rels)
    return [
        ref
        for ref in item.get("refs") or ()
        if wanted is None or ref.get("rel") in wanted
    ]


def _value(item: Item) -> Mapping[str, Any]:
    value = item.get("value")
    return value if isinstance(value, Mapping) else {}


def _kind_of(params: Mapping[str, Any]) -> dict[str, str]:
    """type -> kind, from the catalog's ``kinds`` param ({kind: [types]})."""
    kinds = params.get("kinds") or {}
    return {str(t): str(kind) for kind, types in kinds.items() for t in types or ()}


def _finding(
    rule: str, item: str, message: str, blocking: bool = True
) -> RecordFinding:
    return RecordFinding(
        rule=rule, message=f"{item}: {message}", blocking=blocking, item=item
    )


def _positions(process: Item, contains_rel: str) -> list[tuple[Any, str]]:
    """A process's positions: its contains refs that carry an occurrence, in
    order, as (position id, item id)."""
    return [
        (ref.get("occurrence"), str(ref.get("to")))
        for ref in _refs(process, [contains_rel])
        if ref.get("occurrence") is not None
    ]


# ---------------------------------------------------------------------------
# 1. reference
# ---------------------------------------------------------------------------


# ID: 936dacf9-3162-4c3f-9c2a-f0d5533c3c9f
def reference(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Every ref points to an item in the snapshot."""
    items = record.get("items") or {}
    known = {str(k) for k in record.get("known") or ()}
    findings = []
    for item_id, item in _items(record):
        for ref in _refs(item):
            target = str(ref.get("to"))
            if target in items:
                continue
            why = (
                "id exists but has no usable version on that date"
                if target in known
                else "no such id"
            )
            findings.append(
                _finding(rule, item_id, f"{ref.get('rel')} ref to {target}: {why}")
            )
    return findings


# ---------------------------------------------------------------------------
# 2. role
# ---------------------------------------------------------------------------


# ID: 03377665-49b7-4f79-9142-a082ec1d39e9
def role(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Every owner, and every ref with a role relation, points to a role."""
    items = record.get("items") or {}
    role_type = params.get("role_type", "role")
    rels = params.get("role_rels", ["role", "editor", "holder", "delegate"])
    findings = []
    for item_id, item in _items(record):
        owner = item.get("owner")
        if owner in items and items[owner].get("type") != role_type:
            findings.append(
                _finding(
                    rule,
                    item_id,
                    f"owner {owner} is a {items[owner].get('type')}, not a {role_type}",
                )
            )
        for ref in _refs(item, rels):
            target = ref.get("to")
            if target in items and items[target].get("type") != role_type:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{ref.get('rel')} ref to {target} is a "
                        f"{items[target].get('type')}, not a {role_type}",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 3. composition
# ---------------------------------------------------------------------------


# ID: 112aa6bf-de98-4eaa-8dbc-89da41007c32
def composition(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Every type has a kind; models name one document type; contains refs
    respect the kinds, the catalogue families and the model ranks.

    A model's rank is ``value.rank`` of the document_type item its
    document_type ref points to (rank 1 is the top), never its own value.
    Catalogue types (``catalogue_types``) are models that need no
    document_type ref, have no rank, hold only their family and may sit in
    any model.
    """
    items = record.get("items") or {}
    kind_of = _kind_of(params)
    doc_type = params.get("document_type_type", "document_type")
    doc_type_rel = params.get("document_type_rel", "document_type")
    contains_rel = params.get("contains_rel", "contains")
    catalogues = {str(t) for t in params.get("catalogue_types") or ()}
    families = {
        str(k): {str(t) for t in v or ()}
        for k, v in (params.get("catalogue_families") or {}).items()
    }
    process_types = set(params.get("process_types", ["process"]))
    process_members = set(params.get("process_members", ["step", "decision"]))
    shape = _Shape(items, kind_of, catalogues, doc_type, doc_type_rel)
    findings = []
    for item_id, item in _items(record):
        item_type = str(item.get("type"))
        kind = kind_of.get(item_type)
        if kind is None:
            findings.append(_finding(rule, item_id, f"type {item_type} has no kind"))
            continue
        # a. a model that is not a catalogue has exactly one document_type ref
        if kind == "model" and item_type not in catalogues:
            findings += _document_type_findings(
                rule, item_id, item, items, doc_type, doc_type_rel
            )
        # b. what may contain what
        for ref in _refs(item, [contains_rel]):
            target = ref.get("to")
            if (
                target not in items
                or kind_of.get(str(items[target].get("type"))) is None
            ):
                continue  # missing: left to reference; no kind: reported on the child
            message = _containment(
                item, items[target], shape, families, process_types, process_members
            )
            if message is not None:
                findings.append(
                    _finding(rule, item_id, f"contains {target}: {message}")
                )
    return findings


def _document_type_findings(
    rule: str,
    item_id: str,
    item: Item,
    items: Mapping[Any, Any],
    doc_type: str,
    doc_type_rel: str,
) -> list[RecordFinding]:
    refs = _refs(item, [doc_type_rel])
    findings = []
    if len(refs) != 1:
        findings.append(
            _finding(
                rule,
                item_id,
                f"a model needs exactly one {doc_type_rel} ref, has {len(refs)}",
            )
        )
    for ref in refs:
        target = ref.get("to")
        if target in items and items[target].get("type") != doc_type:
            findings.append(
                _finding(
                    rule,
                    item_id,
                    f"{doc_type_rel} ref to {target} is a "
                    f"{items[target].get('type')}, not a {doc_type}",
                )
            )
    return findings


class _Shape:
    """Kind, catalogue and rank lookups for the containment check."""

    def __init__(
        self,
        items: Mapping[Any, Any],
        kind_of: Mapping[str, str],
        catalogues: set[str],
        doc_type: str,
        doc_type_rel: str,
    ) -> None:
        self.items, self.kind_of, self.catalogues = items, kind_of, catalogues
        self.doc_type, self.doc_type_rel = doc_type, doc_type_rel

    # ID: 8be24aa6-05ad-418b-9cdb-399404a918dd
    def kind(self, item: Item) -> str | None:
        return self.kind_of.get(str(item.get("type")))

    # ID: 6accc763-2799-4f6e-b507-c07795917478
    def is_catalogue(self, item: Item) -> bool:
        return str(item.get("type")) in self.catalogues

    # ID: 53365ab5-443b-4ad9-82b9-cd4461fec907
    def rank(self, model: Item) -> tuple[int | None, str | None]:
        """(rank, problem). The rank is the linked document_type's value.rank.
        (None, None) when it cannot be read because the ref is missing,
        repeated or broken: composition (a) and reference report those."""
        refs = _refs(model, [self.doc_type_rel])
        if len(refs) != 1 or refs[0].get("to") not in self.items:
            return None, None
        target = refs[0].get("to")
        linked = self.items[target]
        if linked.get("type") != self.doc_type:
            return None, None
        rank = _value(linked).get("rank")
        if isinstance(rank, int) and not isinstance(rank, bool):
            return rank, None
        return None, f"{self.doc_type} {target} has no numeric value.rank"


def _containment(
    parent: Item,
    child: Item,
    shape: _Shape,
    families: Mapping[str, set[str]],
    process_types: set[str],
    process_members: set[str],
) -> str | None:
    """Why ``parent`` may not contain ``child``, or None when it may. Both
    have a kind."""
    child_type, parent_type = str(child.get("type")), str(parent.get("type"))
    child_kind, parent_kind = shape.kind(child), shape.kind(parent)
    if child_kind == "document":
        return "a document is never contained"
    if shape.is_catalogue(parent):
        family = families.get(parent_type, set())
        if child_type in family:
            return None
        return f"{child_type} is not in the {parent_type} family {sorted(family)}"
    if parent_type in process_types:
        if child_type in process_members:
            return None
        return f"a {parent_type} holds only {sorted(process_members)}, not {child_type}"
    if child_kind in {"atom", "molecule"}:
        return None
    if child_kind == "model" and parent_kind == "document":
        return None
    if shape.is_catalogue(child) and parent_kind == "model":
        return None
    if child_kind == "model" and parent_kind == "model":
        parent_rank, parent_problem = shape.rank(parent)
        child_rank, child_problem = shape.rank(child)
        if parent_problem or child_problem:
            return parent_problem or child_problem
        if parent_rank is None or child_rank is None:
            return None  # reported by composition (a) or reference
        if child_rank > parent_rank:
            return None
        return (
            "a model holds a model only of a greater rank number "
            f"({child_rank} <= {parent_rank})"
        )
    return f"a {parent_kind} may not hold a {child_kind}"


# ---------------------------------------------------------------------------
# 4. trace
# ---------------------------------------------------------------------------


# ID: 56066668-add2-46a5-928a-faa5606ec8e4
def trace(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """implements runs control -> requirement -> commitment; addresses -> clause."""
    items = record.get("items") or {}
    implements_rel = params.get("implements_rel", "implements")
    addresses_rel = params.get("addresses_rel", "addresses")
    may_implement = {
        str(k): str(v) for k, v in (params.get("implements") or {}).items()
    }
    clause_type = params.get("clause_type", "clause")
    needs_one = set(params.get("must_implement", ["requirement"]))
    findings = []
    for item_id, item in _items(record):
        item_type = str(item.get("type"))
        refs = _refs(item, [implements_rel])
        allowed = may_implement.get(item_type)
        if refs and allowed is None:
            findings.append(
                _finding(
                    rule, item_id, f"a {item_type} may not {implements_rel} anything"
                )
            )
        good = missing = 0
        for ref in refs:
            target = ref.get("to")
            if target not in items:
                missing += 1
                continue
            if allowed is not None and items[target].get("type") != allowed:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{implements_rel} ref to {target} is a "
                        f"{items[target].get('type')}, not a {allowed}",
                    )
                )
            elif allowed is not None:
                good += 1
        if item_type in needs_one and good == 0 and missing == 0:
            findings.append(
                _finding(
                    rule,
                    item_id,
                    f"a {item_type} must {implements_rel} at least one {allowed}",
                )
            )
        for ref in _refs(item, [addresses_rel]):
            target = ref.get("to")
            if target in items and items[target].get("type") != clause_type:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{addresses_rel} ref to {target} is a "
                        f"{items[target].get('type')}, not a {clause_type}",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 5. cross_reference
# ---------------------------------------------------------------------------


# ID: 1bdc706b-2a06-4eb0-bfd2-e84c39b605a7
def cross_reference(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """A cites ref never points to a document."""
    items = record.get("items") or {}
    kind_of = _kind_of(params)
    cites_rel = params.get("cites_rel", "cites")
    findings = []
    for item_id, item in _items(record):
        for ref in _refs(item, [cites_rel]):
            target = ref.get("to")
            if (
                target in items
                and kind_of.get(str(items[target].get("type"))) == "document"
            ):
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{cites_rel} ref to {target} points to a document; "
                        "cite the model behind it",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 6. flow
# ---------------------------------------------------------------------------


# ID: b0c034fa-5ef5-4ebb-919b-d7fa42c01868
def flow(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """The flow links inside each process are well formed."""
    items = record.get("items") or {}
    contains_rel = params.get("contains_rel", "contains")
    process_types = set(params.get("process_types", ["process"]))
    decision_type = params.get("decision_type", "decision")
    branch, loop = params.get("branch_kind", "branch"), params.get("loop_kind", "loop")
    findings = []
    for item_id, process in _items(record):
        if process.get("type") not in process_types:
            continue
        positions = _positions(process, contains_rel)
        index = {pos: i for i, (pos, _) in enumerate(positions)}
        at = dict(positions)
        links = [
            link
            for link in _value(process).get("flow") or ()
            if isinstance(link, Mapping)
        ]
        incoming: set[Any] = set()
        outcome_links: dict[Any, list[Any]] = {}

        def _bad(message: str, _item_id: str = item_id) -> None:
            findings.append(_finding(rule, _item_id, message))

        for n, link in enumerate(links, start=1):
            src, dst = link.get("from"), link.get("to")
            kind, outcome = link.get("kind"), link.get("outcome")
            label = f"flow link {n} ({src} -> {dst})"
            if src not in index or dst not in index:
                _bad(f"{label}: both ends must be positions in the process")
                continue
            incoming.add(dst)
            source = items.get(at[src])
            if source is not None and source.get("type") == decision_type:
                if kind not in (branch, loop):
                    _bad(
                        f"{label}: a link leaving a decision is a {branch} or a {loop}"
                    )
                outcomes = list(_value(source).get("outcomes") or ())
                if outcome not in outcomes:
                    _bad(
                        f"{label}: outcome {outcome!r} is not one of {at[src]}'s outcomes"
                    )
                else:
                    outcome_links.setdefault(src, []).append(outcome)
            elif source is not None and (kind == branch or outcome is not None):
                _bad(f"{label}: only decisions branch or carry an outcome")
            if kind == loop:
                if index[dst] > index[src]:
                    _bad(f"{label}: a {loop} never points forward")
            elif index[dst] <= index[src]:
                _bad(f"{label}: a non-{loop} link never points backward or to itself")
        for pos, target in positions:
            source = items.get(target)
            if source is None or source.get("type") != decision_type:
                continue
            given = outcome_links.get(pos, [])
            for outcome in _value(source).get("outcomes") or ():
                count = given.count(outcome)
                if count != 1:
                    _bad(
                        f"decision at {pos}: outcome {outcome!r} has {count} links, needs exactly one"
                    )
        for pos, _ in positions[1:]:
            if pos not in incoming:
                _bad(f"position {pos} has no incoming link")
    return findings


# ---------------------------------------------------------------------------
# 7. occurrence
# ---------------------------------------------------------------------------


# ID: 55b2aeb9-044b-439c-a617-1a7098c3b6c6
def occurrence(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Position ids are unique; each raci item has an occurrence link, and it
    points to an existing step position. CORE checks the link's presence
    itself rather than relying on the caller's schema check."""
    items = record.get("items") or {}
    contains_rel = params.get("contains_rel", "contains")
    process_types = set(params.get("process_types", ["process"]))
    raci_type = params.get("raci_type", "raci")
    occurrence_rel = params.get("occurrence_rel", "occurrence")
    step_type = params.get("step_type", "step")
    findings = []
    for item_id, item in _items(record):
        if item.get("type") in process_types:
            seen: set[Any] = set()
            for pos, _ in _positions(item, contains_rel):
                if pos in seen:
                    findings.append(
                        _finding(rule, item_id, f"position id {pos!r} is used twice")
                    )
                seen.add(pos)
        if item.get("type") != raci_type:
            continue
        if not _refs(item, [occurrence_rel]):
            findings.append(
                _finding(rule, item_id, f"raci item has no {occurrence_rel} link")
            )
        for ref in _refs(item, [occurrence_rel]):
            target = ref.get("to")
            if target not in items:
                continue
            process = items[target]
            if process.get("type") not in process_types:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{occurrence_rel} ref to {target} is not a process",
                    )
                )
                continue
            at = dict(_positions(process, contains_rel))
            pos = ref.get("occurrence")
            if pos not in at:
                findings.append(
                    _finding(rule, item_id, f"{target} has no position {pos!r}")
                )
                continue
            holder = items.get(at[pos])
            if holder is not None and holder.get("type") != step_type:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"position {pos!r} in {target} holds a {holder.get('type')}, "
                        f"not a {step_type}",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 8. raci
# ---------------------------------------------------------------------------


def _letters(assignment: Any) -> list[str]:
    if isinstance(assignment, str):
        return [ch.upper() for ch in assignment if ch.isalpha()]
    if isinstance(assignment, list | tuple):
        return [str(a).strip().upper() for a in assignment]
    return []


# ID: 597f8bb2-c786-4076-b935-8718a99a2218
def raci(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Each step position has exactly one A and at least one R."""
    items = record.get("items") or {}
    contains_rel = params.get("contains_rel", "contains")
    process_types = set(params.get("process_types", ["process"]))
    raci_type = params.get("raci_type", "raci")
    occurrence_rel = params.get("occurrence_rel", "occurrence")
    step_type = params.get("step_type", "step")
    letters: dict[tuple[str, Any], list[str]] = {}
    for _, item in _items(record):
        if item.get("type") != raci_type:
            continue
        for ref in _refs(item, [occurrence_rel]):
            key = (str(ref.get("to")), ref.get("occurrence"))
            letters.setdefault(key, []).extend(_letters(_value(item).get("assignment")))
    findings = []
    for item_id, process in _items(record):
        if process.get("type") not in process_types:
            continue
        for pos, target in _positions(process, contains_rel):
            holder = items.get(target)
            if holder is None or holder.get("type") != step_type:
                continue
            given = letters.get((item_id, pos), [])
            a, r = given.count("A"), given.count("R")
            if a != 1 or r < 1:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"step at {pos!r} needs exactly one A and at least one R, "
                        f"has {a} A and {r} R",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 9. dressing
# ---------------------------------------------------------------------------


_DRESSING_WORDS = [
    "must", "shall", "require", "requires", "required", "requiring",
    "except", "excepted", "unless",
]  # fmt: skip


# ID: a9079187-c402-402f-98f4-eb138482b88b
def dressing(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """A document's dressing paragraphs use no normative words."""
    kind_of = _kind_of(params)
    words = params.get("words", _DRESSING_WORDS)
    pattern = re.compile(
        r"\b(" + "|".join(map(re.escape, words)) + r")\b", re.IGNORECASE
    )
    findings = []
    for item_id, item in _items(record):
        if kind_of.get(str(item.get("type"))) != "document":
            continue
        for n, paragraph in enumerate(_value(item).get("dressing") or (), start=1):
            if not isinstance(paragraph, str):
                continue
            found = sorted({m.group(1).lower() for m in pattern.finditer(paragraph)})
            if found:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"dressing paragraph {n} uses normative word(s): {', '.join(found)}",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# 10. authority
# ---------------------------------------------------------------------------


# ID: 4ffc6ef7-6da0-4a11-a3d4-598f37092d94
def authority(
    record: Mapping[str, Any], rule: str, params: Mapping[str, Any]
) -> list[RecordFinding]:
    """Authority items carry exactly the links their type needs.

    ``required``: {type: {rel: target type}}, each exactly once.
    ``optional``: {type: {rel: {target: type, max: n | null}}}; null = no limit.
    A missing target is left to ``reference``.
    """
    items = record.get("items") or {}
    required = params.get("required") or {}
    optional = params.get("optional") or {}
    findings = []
    for item_id, item in _items(record):
        item_type = str(item.get("type"))
        needs = required.get(item_type) or {}
        may = optional.get(item_type) or {}
        if not needs and not may:
            continue
        expected: dict[str, str] = {rel: str(t) for rel, t in needs.items()}
        expected.update({rel: str(spec.get("target")) for rel, spec in may.items()})
        for rel in needs:
            count = len(_refs(item, [rel]))
            if count != 1:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"a {item_type} needs exactly one {rel} ref, has {count}",
                    )
                )
        for rel, spec in may.items():
            limit = spec.get("max")
            count = len(_refs(item, [rel]))
            if limit is not None and count > limit:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"a {item_type} has at most {limit} {rel} ref, has {count}",
                    )
                )
        for ref in _refs(item, expected):
            target = ref.get("to")
            want = expected[str(ref.get("rel"))]
            if target in items and items[target].get("type") != want:
                findings.append(
                    _finding(
                        rule,
                        item_id,
                        f"{ref.get('rel')} ref to {target} is a "
                        f"{items[target].get('type')}, not a {want}",
                    )
                )
    return findings


RULES: dict[str, RuleFn] = {
    "reference": reference,
    "role": role,
    "composition": composition,
    "trace": trace,
    "cross_reference": cross_reference,
    "flow": flow,
    "occurrence": occurrence,
    "raci": raci,
    "dressing": dressing,
    "authority": authority,
}
