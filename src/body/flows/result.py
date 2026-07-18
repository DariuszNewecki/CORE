# src/body/flows/result.py
"""
FlowResult — the structured result contract every Flow returns.

Mirrors ActionResult in purpose and shape. FlowExecutor always returns
a FlowResult. Callers (Workers, other Flows) always receive a FlowResult.

Constitutional alignment: CORE-Flow.md §6
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ID: 5b6c8e1a-2d4f-4a37-9b06-c1e3f7a9d502
def declared_production(flow_result: Any) -> set[str] | None:
    """Union of a flow's steps' declared production (ADR-107 D1).

    Reads ``files_produced`` from each step's result data and returns the union
    as an allowlist for ``SandboxLifecycle.propagate_changes``. Returns ``None``
    when NO step declares production (the key is absent on every step) — the
    ADR-107 D4 fallback that keeps un-migrated flows on the full worktree-diff
    behavior. A step that declares ``files_produced`` (even an empty list)
    counts as opted in, so a flow whose only writer wrote nothing propagates
    nothing rather than falling back to the whole diff.

    Public and colocated with FlowResult (rather than private inside
    ProposalExecutor, where it originated) because #814's symbol-level
    remediation orchestrator needs the identical per-flow-result semantic to
    union declared production across multiple flow executions against the
    same worktree — one per symbol, all targeting the same file.
    """
    declared: set[str] = set()
    any_declared = False
    for step in getattr(flow_result, "steps", None) or []:
        data = step.data if isinstance(step.data, dict) else {}
        produced = data.get("files_produced")
        if produced is None:
            continue
        any_declared = True
        for path in produced:
            if isinstance(path, str) and path:
                declared.add(path)
    return declared if any_declared else None


@dataclass
# ID: 9553ab38-2830-4211-ba47-080671561054
class StepResult:
    """
    The result of a single step within a Flow.

    Wraps either an ActionResult (for AtomicAction steps) or a nested
    FlowResult (for nested Flow steps). Carries the step's ref_id and
    required flag so callers can reason about which failures are halting.
    """

    ref_id: str
    """The action_id or flow_id that produced this result."""

    required: bool
    """Whether failure of this step halted the Flow."""

    ok: bool
    """True if the step succeeded."""

    data: dict[str, Any]
    """The result data from the step — ActionResult.data or FlowResult summary."""

    duration_sec: float = 0.0
    """Wall-clock duration of this step."""

    kind: str = "action"
    """'action', 'flow', or 'cognitive' — mirrors StepKind for serialization."""


@dataclass
# ID: cbce2e91-8400-4e8a-ad1c-ff613bb4f771
class FlowResult:
    """
    The structured result contract every Flow execution returns.

    Constitutional requirement (CORE-Flow.md §6):
    FlowExecutor always returns a FlowResult. No exceptions.

    Fields mirror ActionResult where they overlap, so callers that
    handle both types can reason uniformly about ok, duration_sec,
    and data.
    """

    flow_id: str
    """The registered flow_id that produced this result."""

    ok: bool
    """
    True if all required steps succeeded.
    False if any required step returned ok=False or raised.
    Optional steps never affect this field.
    """

    steps: list[StepResult] = field(default_factory=list)
    """Ordered list of StepResults, one per declared step."""

    duration_sec: float = 0.0
    """Total wall-clock duration of the entire Flow."""

    @property
    # ID: adf4ae60-a0b2-4253-9f9d-8d5ab97e375c
    def data(self) -> dict[str, Any]:
        """
        Structured summary of all step outcomes.

        Provided for callers that handle FlowResult and ActionResult
        uniformly and expect a top-level dict on .data.
        """
        return {
            "flow_id": self.flow_id,
            "ok": self.ok,
            "steps": [
                {
                    "ref_id": s.ref_id,
                    "kind": s.kind,
                    "required": s.required,
                    "ok": s.ok,
                    "duration_sec": s.duration_sec,
                    "data": s.data,
                }
                for s in self.steps
            ],
            "duration_sec": self.duration_sec,
        }

    @property
    # ID: 14d32876-6fa9-490b-b5b4-7ab07c4b6445
    def failed_steps(self) -> list[StepResult]:
        """All steps that returned ok=False, required or not."""
        return [s for s in self.steps if not s.ok]

    @property
    # ID: eaa00ab0-9388-42df-858a-6631cfb5d653
    def failed_required_steps(self) -> list[StepResult]:
        """Required steps that returned ok=False — these caused ok=False on the Flow."""
        return [s for s in self.steps if not s.ok and s.required]
