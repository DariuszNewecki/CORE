# src/mind/coherence/checks/specgap.py
"""SPECGAP — upstream normative claim with no downstream operationalizing artifact.

Per ADR-073 D7 + D11. Detects gaps where Northstar (or paper) declares a
required behavior that the corresponding phase YAML's failure_mode does not
address. Vector kNN cannot detect this class — the conflict is absence, not
opposition.

v1 detection rule per D7:
  For each pair (N, P) where N is a Northstar/paper paragraph and P is a
  workflow phase, emit when ALL of:
    1. N qualifies as upstream-normative
    2. N is operationally linked to P (D11 bridge or textual mention)
    3. N contains a required-behavior action verb from D10
    4. The phase YAML exists with a non-empty failure_mode
    5. No failure_mode value overlaps the action-verb signal

No LLM. No vectors.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .base import CoherenceCandidate


if TYPE_CHECKING:
    from body.governance.coherence_harvester import NormativeMarkerRegister


_UR_HEADING = re.compile(r"^###\s+(UR-\d{2}):\s*(.+?)\s*$", re.MULTILINE)


# ID: 8a9fd6fc-ce33-4b47-ba55-fe24b5d37bc5
def _phases() -> tuple[str, ...]:
    """Canonical `phase` membership from .intent/META/enums.json.

    Sourced from the canonical enum store rather than inlined here so
    SpecGap's iteration order tracks the constitutional vocabulary
    without drift (closed-enum discipline, issue #460). Lazy because
    coherence checks are constructed before IntentRepository may be
    fully warm during cold-start scans.
    """
    from shared.infrastructure.intent.canonical_enums import get_enum_members

    return tuple(sorted(get_enum_members("phase")))


# ID: 462e86d4-ce44-4239-8fb0-4efaf0a5278d
class SpecGapCheck:
    """Emit SPECGAP when upstream required behavior has no downstream operationalization."""

    relation = "SPECGAP"

    # ID: 9fb8fe6c-ae8c-4be5-9022-fc6c4ac0c362
    def __init__(self, repo_root: Path, register: NormativeMarkerRegister) -> None:
        self._repo_root = Path(repo_root)
        self._register = register
        self._action_verb_pattern = re.compile(
            "|".join(rf"\b{re.escape(v)}\w*\b" for v in register.action_verbs),
            re.IGNORECASE,
        )

    # ID: 43197388-342a-495c-844f-2889159e9994
    async def run(self) -> list[CoherenceCandidate]:
        phase_modes = self._load_phase_failure_modes()
        responsibility = self._load_phase_responsibility()
        ur_paragraphs = self._extract_ur_paragraphs()

        candidates: list[CoherenceCandidate] = []
        for ur_id, ur_rel, paragraph in ur_paragraphs:
            action_verbs = self._action_verbs_in(paragraph)
            if not action_verbs:
                continue
            for phase in _phases():
                if not self._operationally_linked(
                    ur_id, paragraph, phase, responsibility
                ):
                    continue
                failure_mode = phase_modes.get(phase)
                if not failure_mode:
                    continue
                if self._verbs_covered_by(failure_mode):
                    continue
                phase_rel = f".intent/phases/{phase}.yaml"
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[ur_rel, phase_rel],
                        claim=(
                            f"Northstar §{ur_id} declares required behavior "
                            f"({', '.join(sorted(action_verbs))}) for phase "
                            f"`{phase}`, but `{phase}.yaml`'s failure_mode "
                            f"`{failure_mode}` does not address it."
                        ),
                        rationale=(
                            f"Topology paper §6.1 contradiction invariant via "
                            f"the D11 phase-responsibility bridge identifies "
                            f"`{phase}` as responsible for {ur_id}. The Northstar "
                            f"paragraph asserts the system should "
                            f"{', '.join(sorted(action_verbs))} under some condition, "
                            f"but the phase's only declared failure mode is "
                            f"`{failure_mode}`. Either extend the phase's "
                            "failure_mode vocabulary to cover the upstream "
                            "required behavior, or — if the upstream claim is "
                            "no longer authoritative — amend Northstar."
                        ),
                    )
                )
        return candidates

    def _load_phase_failure_modes(self) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for phase in _phases():
            path = self._repo_root / ".intent" / "phases" / f"{phase}.yaml"
            if not path.exists():
                result[phase] = None
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            result[phase] = data.get("failure_mode")
        return result

    def _load_phase_responsibility(self) -> dict[str, dict]:
        path = (
            self._repo_root
            / ".intent"
            / "enforcement"
            / "config"
            / "phase_responsibility.yaml"
        )
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data.get("phases", {}) or {}

    def _extract_ur_paragraphs(self) -> list[tuple[str, str, str]]:
        path = self._repo_root / ".specs" / "northstar" / "CORE-USER-REQUIREMENTS.md"
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(self._repo_root))
        matches = list(_UR_HEADING.finditer(content))
        result: list[tuple[str, str, str]] = []
        for i, m in enumerate(matches):
            ur_id = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section = content[start:end]
            for paragraph in _iter_paragraphs(section):
                result.append((ur_id, rel, paragraph))
        return result

    # ID: b891e1a5-db39-4243-a3e9-79f5425e8bdc
    def _operationally_linked(
        self,
        ur_id: str,
        paragraph: str,
        phase: str,
        responsibility: dict[str, dict],
    ) -> bool:
        """D7 condition 2: phase mentioned in text OR linked via D11 mapping."""
        phase_entry = responsibility.get(phase) or {}
        if phase_entry.get("cross_cutting"):
            return False
        urs = phase_entry.get("operationalizes_urs") or []
        if ur_id in urs:
            return True
        return _whole_word(paragraph, phase) or _whole_word(paragraph, phase + "s")

    def _action_verbs_in(self, text: str) -> set[str]:
        verbs: set[str] = set()
        for m in self._action_verb_pattern.finditer(text):
            verbs.add(m.group(0).lower())
        return verbs

    # ID: 4b4328d6-4874-4d40-87b8-123c510da8ce
    def _verbs_covered_by(self, failure_mode: str) -> bool:
        """Covered iff failure_mode declares any verb from register.action_verbs (one halt-class today)."""
        return bool(self._action_verb_pattern.search(failure_mode))


def _iter_paragraphs(section: str):
    para: list[str] = []
    for line in section.split("\n"):
        if line.strip():
            para.append(line)
        elif para:
            text = "\n".join(para).strip()
            if text:
                yield text
            para = []
    if para:
        text = "\n".join(para).strip()
        if text:
            yield text


def _whole_word(content: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", content, re.IGNORECASE) is not None
