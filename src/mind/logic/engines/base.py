# src/mind/logic/engines/base.py

"""
Provides the base contract for all constitutional enforcement engines.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to async-first verification to prevent event-loop hijacking
  in I/O-bound engines (Database/Network).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from shared.models.audit_models import EvidenceClass


# Pattern for "Line N:" or "(line N)" embedded in engine violation messages —
# the common pre-#548 shape (e.g. f"Line {node.lineno}: Forbidden primitive...").
# Used by extract_line_number as the regex fallback when no structured
# line key is present in the violation's details.
_EMBEDDED_LINE_RE = re.compile(r"\b[Ll]ine\s+(\d+)\b")


@dataclass
# ID: 5c3cb061-ea3e-46c9-b0a6-baf214a40b26
class EngineResult:
    """The result of a constitutional engine verification run.

    ``violations`` accepts two shapes, normalized by
    :func:`normalize_violation`:

    - ``str``: message-only (e.g. ``"Line 42: use of eval()"``).
      Backwards-compatible — most engines emit this shape.
    - ``dict``: ``{"message": str, "details": dict[str, Any]}``. Carries
      structured signal from sensors that produce it (e.g. modularity's
      ``dominant_class_name``, ``responsibility_count``).

    Consumers MUST call ``normalize_violation(v)`` when iterating
    ``violations``; direct string interpolation will misbehave on dict
    entries. Widened from ``list[str]`` so downstream consumers
    (``rule_executor``, ``AuditFinding.context``) can propagate the
    structural signal sensors already produce.

    ``extra`` carries engine-specific signals that are not violations — e.g.
    the GRC judge's three-way ``coverage`` field (satisfied / gap / silent).
    Consumers that don't recognise the key ignore it; ``rule_executor`` does
    not read it.
    """

    ok: bool
    message: str
    violations: list[str | dict[str, Any]]
    engine_id: str
    extra: dict[str, Any] = field(default_factory=dict)


# ID: a7f3c9d2-5e1b-4f8a-b6d4-9c7e2a1b3f8d
def normalize_violation(v: str | dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Normalize a raw engine violation to ``(message, details)``.

    Engines emit violations either as bare strings (historical) or as
    dicts carrying structured detail (modularity, and any future
    detail-rich sensor). This helper lets every consumer handle both
    shapes uniformly without caring which engine produced the finding.

    Args:
        v: A single item from ``EngineResult.violations``.

    Returns:
        ``(message, details)``. ``details`` is an empty dict for
        string-shaped violations.
    """
    if isinstance(v, dict):
        return str(v.get("message", "")), dict(v.get("details") or {})
    return v, {}


# ID: ef871f89-7261-4682-8f9f-159cab03ac73
def extract_line_number(
    message: str, details: Mapping[str, Any] | None = None
) -> int | None:
    """Extract the violation's line number for ``AuditFinding.line_number``.

    Closes the asymmetry described in #548: many engines know the line
    number of a violation (most parse the file via AST) but embed it in
    the human-readable message string instead of populating the structured
    ``AuditFinding.line_number`` field, so GitHub inline annotations
    default to line 1 of the file rather than landing at the violation.

    Preference order:

    1. ``details["line_number"]`` — the canonical structured key.
    2. ``details["line"]`` — common short alias used by sensors that
       pre-date the canonical key.
    3. Regex fallback: the first ``"Line N"`` / ``"line N"`` match in
       ``message``. This handles the legacy pattern uniformly across
       engines without requiring per-engine updates.

    Returns ``None`` if no extraction succeeds; consumers pass that
    through to ``AuditFinding.line_number=None`` (the field's documented
    "no line info available" sentinel).
    """
    if details:
        for key in ("line_number", "line"):
            value = details.get(key)
            if isinstance(value, int) and value > 0:
                return value
            if isinstance(value, str) and value.isdigit():
                line = int(value)
                if line > 0:
                    return line

    match = _EMBEDDED_LINE_RE.search(message)
    if match:
        line = int(match.group(1))
        if line > 0:
            return line

    return None


# ID: 185ac493-d859-4a19-a7bd-e85fd2239af7
class BaseEngine(ABC):
    """
    Abstract base class for all Governance Engines.

    Now natively async to support the Database-as-SSOT principle
    without violating loop-hijacking rules.
    """

    # ADR-113: how this engine establishes a verdict. The engine is the
    # authority on its own evidence class — the rule_executor stamps it onto
    # every genuine-verdict finding the engine produces. Fail-closed default
    # is ATTESTED ("needs a human"): an engine that forgets to declare its
    # class degrades to the weakest, never to a false PROVEN (ADR-113 D3).
    # Deterministic gates override to PROVEN; llm_gate to JUDGED.
    evidence_class: ClassVar[EvidenceClass] = EvidenceClass.ATTESTED

    # Engines that handle a fixed set of named check_types at context-level
    # declare those names here. is_context_level_for (below) dispatches against
    # this set; no override needed in the subclass. Engines that are always
    # context-level (return True) or have mixed/complex dispatch logic keep
    # their own is_context_level_for override and leave this empty.
    _context_check_types: ClassVar[frozenset[str]] = frozenset()

    @abstractmethod
    # ID: db4c48d2-4ccc-4182-bb37-29973471b8bb
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Verify a file or context against constitutional rules.

        Args:
            file_path: Absolute path to the file being audited.
            params: Rule-specific parameters from the Mind.

        Returns:
            EngineResult indicating compliance status.
        """
        pass

    @classmethod
    # ID: 17cb7c7f-94f3-4d61-8a2c-3a0b9d1e4c2d
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """
        Whether this engine dispatches the given check_type at context-level.

        ADR-076 D1/D2: dispatch mode is engine-declared per check_type, not
        per-engine. Default checks ``cls._context_check_types``; engines with
        a fixed set of named check_types declare them there and need no
        override. Engines that are always context-level (or have mixed/complex
        dispatch) override this method directly.

        Called by the rule extractor on the engine *class* (no instantiation),
        so overrides must be classmethods that depend only on ``check_type``.
        """
        return check_type in cls._context_check_types
