# src/body/governance/coherence_harvester.py
"""
Governance Claim Harvester - Body Layer

Walks the governance corpus (.specs/{decisions,papers,northstar}, .intent/)
and extracts normative claims per ADR-073 D4 / D10. Pure read-only; no DB,
no LLM, no side effects.

Consumed by:
  - will.workers.governance_embedding (steady-state incremental sync)
  - mind.coherence.* (check-class implementations for ROW3_CITATION, SPECGAP)
  - cli.resources.coherence (bootstrap subcommand)

Constitutional grounding:
  - ADR-073 D4 (sync worker harvest)
  - ADR-073 D10 (§2.5 marker register at .intent/enforcement/config/normative_markers.yaml)
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


_MIN_TEXT_LEN = 40
_MAX_TEXT_LEN = 1500

_STRUCTURED_FIELDS = frozenset(
    {"statement", "description", "rationale", "principle", "responsibility", "verdict"}
)


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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        markers = tuple(data.get("markers", []))
        action_verbs = tuple(data.get("action_verbs", []))
        aspirational = tuple(data.get("aspirational_markers", []))
        if not markers:
            raise ValueError(
                f"normative_markers.yaml at {path} has empty markers list — D10 requires non-empty"
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
    """

    # ID: 23757375-49cc-43db-972e-1bb5aaa87502
    def __init__(
        self,
        repo_root: Path,
        register: NormativeMarkerRegister | None = None,
    ) -> None:
        self._repo_root = Path(repo_root).resolve()
        if register is None:
            register_path = (
                self._repo_root
                / ".intent"
                / "enforcement"
                / "config"
                / "normative_markers.yaml"
            )
            register = NormativeMarkerRegister.from_yaml(register_path)
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

        intent_root = self._repo_root / ".intent"
        if intent_root.is_dir():
            for path in sorted(intent_root.rglob("*.json")):
                if "META" in path.parts:
                    continue
                yield from self._extract_structured(path)
            for path in sorted(intent_root.rglob("*.yaml")):
                if "META" in path.parts:
                    continue
                yield from self._extract_structured(path)

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

    def _extract_structured(self, path: Path) -> Iterator[Claim]:
        try:
            if path.suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
            else:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("harvester: failed to parse %s: %s", path, exc)
            return
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
