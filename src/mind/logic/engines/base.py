# src/mind/logic/engines/base.py

"""
Provides the base contract for all constitutional enforcement engines.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to async-first verification to prevent event-loop hijacking
  in I/O-bound engines (Database/Network).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
    """

    ok: bool
    message: str
    violations: list[str | dict[str, Any]]
    engine_id: str


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


# ID: 185ac493-d859-4a19-a7bd-e85fd2239af7
class BaseEngine(ABC):
    """
    Abstract base class for all Governance Engines.

    Now natively async to support the Database-as-SSOT principle
    without violating loop-hijacking rules.
    """

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
