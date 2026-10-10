# src/shared/infrastructure/assistant_surface/law_facts.py

"""Law & facts: grounded answers with provenance (ADR-168 D2).

Every answer names its class and its sources. The epistemic contract:

- **law**: authoritative ``.intent/`` content, read through IntentRepository;
- **repository fact**: observed deterministically from the repository;
- **decision history**: accepted ADRs and other ``.specs/`` evidence;
- **unknown**: returned as unknown, never upgraded to a fact.

Inference about intent is out of scope: no answer says what the governor
"probably" meant. The service returns facts with provenance, not context.

Read-only and deterministic: no database, no LLM, no writes. Bound to one
repository root, so it answers for CORE and for an adopter project alike.
"""

from __future__ import annotations

import importlib.resources
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.intent_repository import IntentRepository
from shared.logger import getLogger


logger = getLogger(__name__)

LAW = "law"
REPOSITORY_FACT = "repository_fact"
DECISION_HISTORY = "decision_history"
UNKNOWN = "unknown"

_ADR_DIR = Path(".specs") / "decisions"
_ADR_FILE = re.compile(r"^ADR-(\d+)[-.].*\.md$")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_INTENT_GUARD = "IntentGuard"
_FLOOR_VERDICT_POLICY = "enforcement/config/audit_verdict.yaml"


@dataclass(frozen=True)
# ID: cce13c51-d165-489f-a211-5d1066e6f812
class Source:
    """Where an answer comes from: a repository-relative path and, optionally,
    the element within it (a rule id, an ADR id, a policy key)."""

    path: str
    locator: str | None = None

    # ID: 2c333160-26ae-43d6-8b47-38b74dd47f5f
    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "locator": self.locator}


@dataclass(frozen=True)
# ID: 87fb39f6-d0e2-47bb-8e4a-e9b3bed5e779
class Answer:
    """One provenance-bearing answer. ``limits`` states, in plain words, what
    the answer does not establish."""

    question: str
    fact_class: str
    answer: dict[str, Any]
    sources: tuple[Source, ...] = ()
    limits: tuple[str, ...] = field(default=())

    # ID: c94b2880-5411-484d-ba9d-80411f9bafbe
    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "class": self.fact_class,
            "answer": self.answer,
            "sources": [s.as_dict() for s in self.sources],
            "limits": list(self.limits),
        }


# ID: 57423956-993f-4506-bafd-0bbdaeab5fad
class LawFacts:
    """Law & facts for one repository (CORE or an adopter project)."""

    def __init__(self, repo_root: Path) -> None:
        self._root = Path(repo_root).resolve()
        self._intent = IntentRepository(strict=False, root=self._root / ".intent")

    # -- law ------------------------------------------------------------------

    # ID: 855c9ae5-bdff-4c40-862f-1edaf52f7dcd
    def rule(self, rule_id: str) -> Answer:
        """The rule as declared: statement, enforcement, authority, phase, the
        mechanism its mapping names, and both source files."""
        question = f"What does rule {rule_id} say?"
        try:
            ref = self._intent.get_rule(rule_id)
        except GovernanceError:
            return Answer(
                question,
                UNKNOWN,
                {"rule_id": rule_id, "declared": False},
                limits=(f"No rule {rule_id!r} is declared in this repository's law.",),
            )
        content = ref.content
        mapping, mapping_path = self._mapping_for(rule_id)
        sources = [Source(self._rel(ref.source_path), rule_id)]
        answer: dict[str, Any] = {
            "rule_id": rule_id,
            "declared": True,
            "statement": content.get("statement"),
            "enforcement": content.get("enforcement"),
            "authority": content.get("authority"),
            "phase": content.get("phase"),
            "mechanism": None,
        }
        limits: list[str] = []
        if mapping is not None and mapping_path is not None:
            params = mapping.get("params") or {}
            answer["mechanism"] = {
                "engine": mapping.get("engine"),
                "enforced_by": params.get("enforced_by"),
                "note": _squash(params.get("enforcement_note")),
            }
            sources.append(Source(self._rel(mapping_path), rule_id))
        else:
            limits.append("No enforcement mapping names a mechanism for this rule.")
        return Answer(question, LAW, answer, tuple(sources), tuple(limits))

    # ID: 10a1ca3e-61c7-41d1-9c88-1f52dadc2d3e
    def can_write(self, path: str) -> Answer:
        """May a producer write ``path``? Answers in two parts, never collapsed
        into one word: what the law says, and what actually enforces it — on
        CORE's own write path and for an external assistant editing the
        working tree directly."""
        question = f"May a producer write {path}?"
        rel = self._repo_relative(path)
        if rel is None:
            return Answer(
                question,
                UNKNOWN,
                {"path": path},
                limits=(
                    "The path is outside this repository; CORE's law does not reach it.",
                ),
            )
        if not (rel == ".intent" or rel.startswith(".intent/")):
            return Answer(
                question,
                LAW,
                {
                    "path": rel,
                    "law": "no location-based prohibition found",
                    "rules": [],
                },
                limits=(
                    "Only location-based write prohibitions are checked here. Whether a "
                    "change at this path is acceptable is decided by the verdict, which "
                    "judges content against the governed rules.",
                ),
            )

        rules, sources = self._rules_enforced_by(_INTENT_GUARD)
        drift_source = self._floor_law_drift_source()
        external = (
            "Not prevented by CORE: an assistant editing the working tree directly is "
            "not intercepted. CORE detects it: uncommitted .intent/ changes make every "
            "audit verdict DEGRADED and name the changed paths (law drift)."
            if drift_source is not None
            else "Not prevented by CORE: an assistant editing the working tree directly "
            "is not intercepted."
        )
        if drift_source is not None:
            sources = (*sources, drift_source)
        answer = {
            "path": rel,
            "law": "forbidden"
            if rules
            else "no rule in this repository's law forbids it",
            "rules": rules,
            "core_write_path": (
                "Refused: IntentGuard's hard invariant blocks every write under .intent/ "
                "made through CORE (FileHandler), whatever the caller."
            ),
            "external_producer": external,
        }
        limits = (
            "Whether a commit carrying such an edit can land depends on the repository "
            "host's settings (for example branch protection and required checks), which "
            "CORE cannot observe from the repository.",
        )
        return Answer(question, LAW, answer, sources, limits)

    # -- decision history -------------------------------------------------------

    # ID: f42fedc4-0a65-4734-b44c-a15e5a06d66d
    def adr(self, adr_id: str) -> Answer:
        """One ADR's identity and status, with its file. ``adr_id`` is
        ``ADR-168`` or ``168``."""
        number = _adr_number(adr_id)
        question = f"What is {adr_id}?"
        if number is None:
            return Answer(
                question, UNKNOWN, {"adr": adr_id}, limits=("Not an ADR id.",)
            )
        for path, meta in self._adr_files():
            if meta.get("number") == number:
                return Answer(
                    question,
                    DECISION_HISTORY,
                    meta | {"decisions": _decision_headings(path)},
                    (Source(self._rel(path), meta.get("id")),),
                )
        return Answer(
            question,
            UNKNOWN,
            {"adr": adr_id},
            limits=(f"No ADR numbered {number} exists in this repository.",),
        )

    # ID: 1451e18a-4f99-487b-b423-fa6275ecffb3
    def adrs(self, status: str | None = None) -> Answer:
        """Every ADR's id, title and status; optionally only those whose status
        begins with ``status`` (for example ``accepted``)."""
        question = "Which ADRs exist" + (f" with status {status}?" if status else "?")
        rows = []
        for path, meta in self._adr_files():
            if status and not str(meta.get("status", "")).lower().startswith(
                status.lower()
            ):
                continue
            rows.append(meta | {"path": self._rel(path)})
        if not (self._root / _ADR_DIR).is_dir():
            return Answer(
                question,
                UNKNOWN,
                {"adrs": []},
                limits=("This repository has no .specs/decisions/ directory.",),
            )
        return Answer(
            question,
            DECISION_HISTORY,
            {"adrs": rows, "count": len(rows)},
            (Source(_ADR_DIR.as_posix()),),
        )

    # ID: 0d35ad3c-ceaa-497f-aaf1-8c4094a7f7a1
    def decisions_mentioning(self, paths: list[str]) -> Answer:
        """For each repository path, the ADRs whose text names it — by path,
        or for a ``src/`` Python file also by its dotted module name.

        Step 0 "was it already decided?" (ADR-168 Amendment 2026-10-10 R4).
        A mention is a textual fact, not a ruling that the ADR governs the
        file; each row carries the ADR's status so a superseded decision is
        visible as such.
        """
        question = "Which decisions mention these files?"
        adrs = [
            (meta, path.read_text(encoding="utf-8", errors="replace"))
            for path, meta in self._adr_files()
        ]
        rows: dict[str, list[dict[str, Any]]] = {}
        for rel in paths:
            needles = _mention_needles(rel)
            rows[rel] = [
                {
                    "id": meta.get("id"),
                    "title": meta.get("title"),
                    "status": meta.get("status"),
                }
                for meta, text in adrs
                if any(needle in text for needle in needles)
            ]
        limits = (
            "Textual mention only: an ADR that governs a file without naming it "
            "is not found, and a mention is not a ruling.",
        )
        return Answer(
            question,
            DECISION_HISTORY,
            {"mentions": rows},
            (Source(_ADR_DIR.as_posix()),),
            limits,
        )

    # -- internals ----------------------------------------------------------------

    def _mappings(self) -> list[tuple[Path, dict[str, Any]]]:
        out: list[tuple[Path, dict[str, Any]]] = []
        for path, doc in self._intent.iter_documents(under="enforcement/mappings"):
            mappings = doc.get("mappings") if isinstance(doc, dict) else None
            if isinstance(mappings, dict):
                out.append((path, mappings))
        return out

    def _mapping_for(self, rule_id: str) -> tuple[dict[str, Any] | None, Path | None]:
        for path, mappings in self._mappings():
            entry = mappings.get(rule_id)
            if isinstance(entry, dict):
                return entry, path
        return None, None

    def _rules_enforced_by(
        self, mechanism: str
    ) -> tuple[list[dict[str, Any]], tuple[Source, ...]]:
        """Declared rules whose mapping names ``mechanism`` as the enforcer,
        each with its own statement, so a reader sees which applies where."""
        rules: list[dict[str, Any]] = []
        sources: list[Source] = []
        for path, mappings in self._mappings():
            for rule_id, entry in sorted(mappings.items()):
                params = entry.get("params") if isinstance(entry, dict) else None
                enforced_by = str((params or {}).get("enforced_by") or "")
                if not enforced_by.endswith(mechanism):
                    continue
                try:
                    ref = self._intent.get_rule(rule_id)
                except GovernanceError:
                    continue
                rules.append(
                    {
                        "rule_id": rule_id,
                        "statement": ref.content.get("statement"),
                        "enforcement": ref.content.get("enforcement"),
                    }
                )
                sources.append(Source(self._rel(ref.source_path), rule_id))
                sources.append(Source(self._rel(path), rule_id))
        return rules, tuple(sources)

    def _floor_law_drift_source(self) -> Source | None:
        """The substrate verdict minimum every project inherits (#952). Cited
        only when it actually declares the law_drift precondition."""
        try:
            floor = importlib.resources.files("shared._machinery_floor")
            text = floor.joinpath(_FLOOR_VERDICT_POLICY).read_text(encoding="utf-8")
            policy = yaml.safe_load(text) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.debug("floor verdict policy unreadable: %s", exc)
            return None
        if "law_drift" not in (policy.get("degraded_on") or []):
            return None
        return Source(
            f"core-runtime: shared/_machinery_floor/{_FLOOR_VERDICT_POLICY}",
            "degraded_on.law_drift",
        )

    def _adr_files(self) -> list[tuple[Path, dict[str, Any]]]:
        base = self._root / _ADR_DIR
        if not base.is_dir():
            return []
        out: list[tuple[Path, dict[str, Any]]] = []
        for path in sorted(base.iterdir()):
            match = _ADR_FILE.match(path.name)
            if not match:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            front = _FRONTMATTER.match(text)
            data: dict[str, Any] = {}
            if front:
                try:
                    loaded = yaml.safe_load(front.group(1))
                    data = loaded if isinstance(loaded, dict) else {}
                except yaml.YAMLError:
                    data = {}
            out.append(
                (
                    path,
                    {
                        "number": int(match.group(1)),
                        "id": data.get("id") or f"ADR-{match.group(1)}",
                        "title": data.get("title"),
                        "status": data.get("status"),
                    },
                )
            )
        return out

    def _repo_relative(self, path: str) -> str | None:
        """Canonical repository-relative path, or None when it resolves outside."""
        candidate = Path(path)
        absolute = (
            candidate if candidate.is_absolute() else self._root / candidate
        ).resolve()
        try:
            return absolute.relative_to(self._root).as_posix()
        except ValueError:
            return None

    def _rel(self, path: Path) -> str:
        try:
            return Path(path).resolve().relative_to(self._root).as_posix()
        except ValueError:
            return str(path)


def _adr_number(adr_id: str) -> int | None:
    match = re.fullmatch(r"(?:ADR-?)?0*(\d+)", adr_id.strip(), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _decision_headings(path: Path) -> list[str]:
    """The ADR's decision headings (``### D1 — …``), in order."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        line.lstrip("#").strip()
        for line in text.splitlines()
        if re.match(r"^#{2,3} D\d+", line)
    ]


def _squash(value: Any) -> str | None:
    return " ".join(str(value).split()) if value else None


def _mention_needles(rel: str) -> tuple[str, ...]:
    """The strings that name *rel* in prose: the path, and for src/**.py the
    dotted module (``src/will/autonomy/proposal.py`` -> ``will.autonomy.proposal``)."""
    needles = [rel]
    if rel.startswith("src/") and rel.endswith(".py"):
        module = rel[len("src/") : -len(".py")].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        needles.append(module)
    return tuple(needles)
