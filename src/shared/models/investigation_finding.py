# src/shared/models/investigation_finding.py

"""Structured findings produced by a read-only investigation (#895 U2).

A finding is evidence, not a verdict. It states what was observed about a target
and points at what supports that statement; it never declares a pass or a fail.
That separation is what lets Trial 0 score recall against a sealed answer key
without the runner having graded itself along the way.

CONSTITUTIONAL:
- Shared layer: no imports from mind/, body/ or will/.
- Immutable: a finding records an observation already made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
# ID: 08b3b136-c8da-49e6-852b-ad7f34c1fd6a
class InvestigationFinding:
    """One observation about a target, with the evidence that supports it.

    Attributes:
        path: Target-relative path the finding concerns, or "" when it concerns
            the target as a whole.
        scope: What the statement ranges over -- a single file, a directory, or
            the whole target.
        category: The kind of observation, from the investigation step that
            produced it.
        statement: What was observed, in one sentence. Not a judgement.
        evidence_refs: Pointers to what supports the statement -- paths, record
            subjects, digests. A finding with no evidence is an assertion.
        authority: The rule or document the observation is made under, when one
            applies. Absent means the observation stands on its own evidence.
        confidence: 1.0 for a deterministic observation. Lower values belong to
            inferred findings and must be justified by the producing step.
    """

    path: str
    scope: str
    category: str
    statement: str
    evidence_refs: list[str] = field(default_factory=list)
    authority: str | None = None
    confidence: float = 1.0

    # ID: 0fab4389-4890-469d-b610-c389f5697936
    def as_payload(self) -> dict[str, Any]:
        """Return the finding as a blackboard-safe payload.

        ``authority`` is omitted rather than serialised as null when absent: a
        missing key says "no authority applies", where an explicit null invites
        the reader to wonder which authority failed to resolve.
        """
        payload: dict[str, Any] = {
            "path": self.path,
            "scope": self.scope,
            "category": self.category,
            "statement": self.statement,
            "evidence_refs": list(self.evidence_refs),
            "confidence": self.confidence,
        }
        if self.authority is not None:
            payload["authority"] = self.authority
        return payload
