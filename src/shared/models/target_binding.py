# src/shared/models/target_binding.py
"""
TargetBinding -- the facts a goal-driven run carries about the repository
it was bound to (ADR-159 Note 2026-09-15, #894 Condition 2 / Unit 3).

Set on ``CoreContext.target_binding`` by ``core-admin runtime external-run``
after bootstrap; ``None`` for a CORE-internal run. ``GoalExecutionWorker``
spreads it into ``goal_run.<run_id>.start`` so the Blackboard -- and #893's
export -- can state which subject a run was about, which execution copy
it ran in, which floor and overlay were installed, and which subject floor
files the floor displaced. Nothing here is a special case for external
runs: the payload carries what the binding supplied, or nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
# ID: 9f2630ba-afe0-4c3a-acfa-b93e6a1f700b
class DisplacedFile:
    """One subject floor file the framework-owned floor replaced in the copy."""

    path: str
    original_sha256: str
    installed_floor_sha256: str


@dataclass(frozen=True)
# ID: 1845a321-feaa-4f66-bae9-a9d048f8346a
class TargetBinding:
    """Binding facts for one run; every field is a plain JSON-able value."""

    subject_path: str
    subject_sha: str
    subject_tree_hash: str
    bound_repo_path: str
    bound_sha: str
    bound_tree_hash: str
    floor_hash: str
    overlay_hash: str
    displaced: tuple[DisplacedFile, ...] = field(default_factory=tuple)

    # ID: 696b3171-1cc8-47a2-9e01-6139ce4d6e93
    def to_payload(self) -> dict[str, Any]:
        """The ``target_binding`` object as recorded on the Blackboard."""
        return {
            "subject_path": self.subject_path,
            "subject_sha": self.subject_sha,
            "subject_tree_hash": self.subject_tree_hash,
            "bound_repo_path": self.bound_repo_path,
            "bound_sha": self.bound_sha,
            "bound_tree_hash": self.bound_tree_hash,
            "floor_hash": self.floor_hash,
            "overlay_hash": self.overlay_hash,
            "displaced": [
                {
                    "path": d.path,
                    "original_sha256": d.original_sha256,
                    "installed_floor_sha256": d.installed_floor_sha256,
                }
                for d in self.displaced
            ],
        }


REQUIRED_BINDING_KEYS: frozenset[str] = frozenset(
    {
        "subject_path",
        "subject_sha",
        "subject_tree_hash",
        "bound_repo_path",
        "bound_sha",
        "bound_tree_hash",
        "floor_hash",
        "overlay_hash",
        "displaced",
    }
)


# ID: d946d1c6-869c-4eda-97dc-acfdbe4b54c9
def validate_binding_payload(value: Any) -> str | None:
    """Return a reason the recorded ``target_binding`` is malformed, else None.

    Used by the run export so a corrupted or partial record refuses rather
    than reconstructing a run "about" an unknown repository.
    """
    if not isinstance(value, dict):
        return f"target_binding is not an object (got {type(value).__name__})"
    missing = sorted(REQUIRED_BINDING_KEYS - set(value))
    if missing:
        return f"target_binding missing keys: {', '.join(missing)}"
    for key in REQUIRED_BINDING_KEYS - {"displaced"}:
        if not isinstance(value[key], str) or not value[key]:
            return f"target_binding.{key} must be a non-empty string"
    displaced = value["displaced"]
    if not isinstance(displaced, list):
        return "target_binding.displaced must be a list"
    for i, item in enumerate(displaced):
        if not isinstance(item, dict) or set(item) != {
            "path",
            "original_sha256",
            "installed_floor_sha256",
        }:
            return f"target_binding.displaced[{i}] has the wrong shape"
    return None
