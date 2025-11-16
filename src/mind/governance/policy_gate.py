# src/mind/governance/policy_gate.py
"""Provides functionality for the policy_gate module."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

try:
    # Prefer your shared exception if present
    from shared.exceptions import PolicyViolation  # type: ignore
except Exception:  # pragma: no cover
    # ID: da8adaec-6f04-43f8-af55-c74f1297408a
    class PolicyViolation(RuntimeError):
        pass


@dataclass(frozen=True)
# ID: a295c1de-3832-47fb-b9b5-7291dc2f8ddb
class ActionStep:
    """
    Minimal, execution-agnostic view of an action step.
    Only the fields needed for policy checks are required.
    """

    name: str  # e.g. "file.format.black"
    target_path: str | None  # repo-relative path, if any
    metadata: Mapping[str, object]  # free-form, e.g. {"evidence": {...}}


@dataclass(frozen=True)
# ID: 1902366c-e06c-4535-aa72-b276cadd813b
class MicroProposalPolicy:
    """
    Minimal view of the runtime policy. Keep it tolerant to your policy YAML.
    """

    allowed_actions: Iterable[str]  # list of glob patterns
    allowed_paths: Iterable[str]  # list of glob patterns (repo-relative)
    required_evidence: Mapping[str, Iterable[str]]  # action_name -> evidence keys

    @classmethod
    # ID: c1514f13-8715-4a4f-a1b5-8e7288bee62c
    def from_dict(cls, d: Mapping[str, object]) -> MicroProposalPolicy:
        return cls(
            allowed_actions=tuple(d.get("allowed_actions", []) or []),
            allowed_paths=tuple(d.get("allowed_paths", []) or []),
            required_evidence=dict(d.get("required_evidence", {}) or {}),
        )


def _match_any(value: str, patterns: Iterable[str]) -> bool:
    # Empty patterns means "no restriction" (i.e., allow anything)
    ps = tuple(patterns)
    if not ps:
        return True
    return any(fnmatch(value, p) for p in ps)


def _require_evidence(step: ActionStep, policy: MicroProposalPolicy) -> None:
    required = policy.required_evidence.get(step.name, [])
    if not required:
        return
    ev = step.metadata.get("evidence", {}) if step.metadata else {}
    missing = [k for k in required if k not in (ev or {})]
    if missing:
        raise PolicyViolation(
            f"Policy requires evidence {missing} for action '{step.name}', none/missing provided."
        )


# ID: 91dcc541-3458-4fd1-9e33-d95a2a101d6d
def enforce_step(
    *,
    step: ActionStep,
    policy: MicroProposalPolicy,
    repo_root: Path,
) -> None:
    """
    Enforce: allowed_actions, allowed_paths, required_evidence.
    - If a field isn't constrained in policy, it doesn't block.
    - Raises PolicyViolation on any breach.
    """
    # 1) action whitelist (glob-friendly)
    if not _match_any(step.name, policy.allowed_actions):
        raise PolicyViolation(
            f"Action '{step.name}' is not permitted by policy.allowed_actions."
        )

    # 2) path whitelist (repo-relative, glob-friendly)
    if step.target_path:
        rel = str(Path(step.target_path).as_posix())
        if not _match_any(rel, policy.allowed_paths):
            raise PolicyViolation(
                f"Target path '{rel}' is not permitted by policy.allowed_paths."
            )

        # Guard against path traversal outside repo root
        abs_target = (repo_root / rel).resolve()
        if (
            repo_root.resolve() not in abs_target.parents
            and abs_target != repo_root.resolve()
        ):
            raise PolicyViolation(
                f"Target path '{rel}' resolves outside repository root."
            )

    # 3) evidence requirements
    _require_evidence(step, policy)
