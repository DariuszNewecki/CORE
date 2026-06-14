# src/shared/governance/coherence_harvester.py
"""
Governance Claim Harvester — Shared utility.

Walks the governance corpus (.specs/{decisions,papers,northstar} via direct
filesystem reads, and .intent/ via the IntentRepository gateway) and yields
typed normative claims. Pure read-only; no DB, no LLM, no side effects.

Consumed by:
  - mind.coherence.* (check-class implementations for ROW3_CITATION, SAMECONCERN, R1_SCOPED, SPECGAP)
  - will.workers.governance_embedding (steady-state incremental sync)
  - cli.resources.coherence (bootstrap subcommand)

Lives in shared/ per architecture.shared.no_strategic_decisions: this module
is a utility — every harvested Claim is data, not a decision. Strategic
interpretation happens in consumers (the check classes, embedder, judge).

.intent/ reads route through IntentRepository.iter_documents (the canonical
gateway), satisfying architecture.namespace.no_direct_protected_access
(formerly architecture.intent.non_gateway_no_direct_resolution; renamed #490).

Constitutional grounding:
  - ADR-073 D4 (sync worker harvest)
  - ADR-073 D10 (§2.5 marker register at .intent/enforcement/config/normative_markers.yaml)
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.intent.intent_repository import IntentRepository


logger = getLogger(__name__)


_MIN_TEXT_LEN = 40
_MAX_TEXT_LEN = 1500

_STRUCTURED_FIELDS = frozenset(
    {"statement", "description", "rationale", "principle", "responsibility", "verdict"}
)

_NORMATIVE_MARKERS_REL = "enforcement/config/normative_markers.yaml"


@dataclass(frozen=True)
# ID: 86c5a6f4-eb32-415b-9830-b88db0dfe8e5
class Claim:
    """One harvested normative claim from a governance artifact."""

    text: str
    source_path: str
    line: int
    paragraph_index: int
    category: str
    content_sha: str


@dataclass(frozen=True)
# ID: d1167a15-c8de-4d91-9e4b-9c814d4eadda
class NormativeMarkerRegister:
    """Loaded contents of .intent/enforcement/config/normative_markers.yaml."""

    markers: tuple[str, ...]
    action_verbs: tuple[str, ...]
    aspirational_markers: tuple[str, ...]
    marker_pattern: re.Pattern[str] = field(repr=False)

    @classmethod
    # ID: a3523853-4dd5-4941-8c6d-d51831c9da31
    def from_yaml(cls, path: Path) -> NormativeMarkerRegister:
        """Legacy constructor — reads a yaml file directly.

        Kept for test ergonomics and ad-hoc CLI use. Production callers
        in src/ should prefer from_intent so .intent/ access stays
        gateway-routed.
        """
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls._from_data(data, source=str(path))

    @classmethod
    # ID: 8f3e1a72-5c4b-4d6e-9a0f-7b2c8d4e6f10
    def from_intent(cls, intent_repo: IntentRepository) -> NormativeMarkerRegister:
        """Canonical constructor — loads via IntentRepository gateway."""
        register_path = intent_repo.resolve_rel(_NORMATIVE_MARKERS_REL)
        data = intent_repo.load_document(register_path)
        return cls._from_data(data, source=str(register_path))

    @classmethod
    def _from_data(
        cls, data: dict[str, Any] | None, *, source: str
    ) -> NormativeMarkerRegister:
        data = data or {}
        markers = tuple(data.get("markers", []))
        action_verbs = tuple(data.get("action_verbs", []))
        aspirational = tuple(data.get("aspirational_markers", []))
        if not markers:
            raise ValueError(
                f"normative_markers register at {source} has empty markers list — D10 requires non-empty"
            )
        pattern = re.compile(
            "|".join(rf"\b{re.escape(m)}\b" for m in markers),
            re.IGNORECASE,
        )
        return cls(markers, action_verbs, aspirational, pattern)


# ID: 392dcaf3-1927-4657-8798-8bee3fd47ab1
class GovernanceClaimHarvester:
    """Walks the governance corpus and yields normative claims.

    Pure read-only. No DB. No LLM. Deterministic over corpus + register.

    .intent/ reads route through the injected IntentRepository (canonical
    gateway). .specs/ reads use direct filesystem access — the
    namespace.no_direct_protected_access rule governs .intent/ only.
    """

    # ID: 23757375-49cc-43db-972e-1bb5aaa87502
    def __init__(
        self,
        repo_root: Path,
        register: NormativeMarkerRegister | None = None,
        intent_repo: IntentRepository | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        if intent_repo is None:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            intent_repo = get_intent_repository()
        self._intent_repo = intent_repo
        if register is None:
            register = NormativeMarkerRegister.from_intent(intent_repo)
        self._register = register

    @property
    # ID: 87a523df-9e4f-478e-87ef-b70bc0fad200
    def register(self) -> NormativeMarkerRegister:
        return self._register

    # ID: 35d0baee-cf39-4fc8-9530-6276cc8568ae
    def harvest(self) -> Iterator[Claim]:
        """Yield every Claim across the governance corpus."""
        roots = [
            (self._repo_root / ".specs" / "decisions", "adr", "*.md"),
            (self._repo_root / ".specs" / "papers", "paper", "*.md"),
            (self._repo_root / ".specs" / "northstar", "northstar", "*.md"),
        ]
        for root, category, glob in roots:
            if not root.is_dir():
                continue
            for path in sorted(root.glob(glob)):
                yield from self._extract_markdown(path, category)

        for path, data in self._intent_repo.iter_documents(skip_components={"META"}):
            yield from self._extract_structured(path, data)

    # ID: b3e40f83-334f-427f-8fab-85ad189875cf
    def _extract_markdown(self, path: Path, category: str) -> Iterator[Claim]:
        content = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(self._repo_root))
        lines = content.split("\n")
        para: list[str] = []
        para_start = 1
        para_idx = 0
        for i, line in enumerate(lines, start=1):
            if line.strip():
                if not para:
                    para_start = i
                para.append(line)
            elif para:
                claim = self._maybe_claim(para, rel, para_start, para_idx, category)
                if claim is not None:
                    yield claim
                    para_idx += 1
                para = []
        if para:
            claim = self._maybe_claim(para, rel, para_start, para_idx, category)
            if claim is not None:
                yield claim

    def _maybe_claim(
        self,
        para: list[str],
        rel: str,
        para_start: int,
        para_idx: int,
        category: str,
    ) -> Claim | None:
        text = "\n".join(para).strip()
        if len(text) < _MIN_TEXT_LEN:
            return None
        if not self._register.marker_pattern.search(text):
            return None
        truncated = text[:_MAX_TEXT_LEN]
        return Claim(
            text=truncated,
            source_path=rel,
            line=para_start,
            paragraph_index=para_idx,
            category=category,
            content_sha=self._sha(truncated),
        )

    def _extract_structured(self, path: Path, data: object) -> Iterator[Claim]:
        if data is None:
            return

        rel = str(path.relative_to(self._repo_root))
        idx = 0
        for value in _walk_strings(data):
            if len(value) < _MIN_TEXT_LEN:
                continue
            if not self._register.marker_pattern.search(value) and len(value) < 100:
                continue
            if not self._register.marker_pattern.search(value):
                continue
            truncated = value[:_MAX_TEXT_LEN].strip()
            yield Claim(
                text=truncated,
                source_path=rel,
                line=1,
                paragraph_index=idx,
                category="intent",
                content_sha=self._sha(truncated),
            )
            idx += 1

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _walk_strings(node: object) -> Iterator[str]:
    """Yield string values nested under recognised normative fields."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and key in _STRUCTURED_FIELDS:
                yield value
            else:
                yield from _walk_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_strings(item)
