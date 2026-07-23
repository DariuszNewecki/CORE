# src/cli/logic/demo/models.py
"""
Typed records for the isolated consequence-chain demo substrate (ADR-155).

Phase 1 populates ``RunIdentity`` and ``IsolationFingerprint`` in full.
``AssertionResult``/``PhaseResult`` are the shell Phase 2's chain-scenario
assertions (D10's full 15-assertion model) and Phase 3's CLI evidence
rendering (D12) both build on — defined here so later phases extend this
shell rather than redefining the wire types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
# ID: b41c9665-8040-4b81-98d9-609db13faeae
class RunIdentity:
    """Opaque identity for one demo run (ADR-155 D3).

    ``run_id`` is the only handle callers pass between substrate steps;
    every other path is derived from it plus ``state_dir``.
    """

    run_id: str
    state_dir: Path
    marker_path: Path
    clone_dir: Path


@dataclass(frozen=True)
# ID: a25cb366-3f7a-42f1-b661-c645449082e2
class IsolationFingerprint:
    """Byte-identity snapshot of the invoking repo (ADR-155 D2/D10 assertion 15).

    ``untracked_files`` maps each pre-existing untracked path to its content
    hash, so a before/after comparison can prove not just that tracked
    HEAD/index are unchanged but that no pre-existing untracked byte was
    touched either.
    """

    head_sha: str
    index_tree_sha: str
    tracked_tree_sha: str
    untracked_files: dict[str, str]

    # ID: 3d4b3fb2-8fe8-41af-b035-b2f6987a89a8
    def matches(self, other: IsolationFingerprint) -> bool:
        """Return True if two fingerprints are byte-identical."""
        return (
            self.head_sha == other.head_sha
            and self.index_tree_sha == other.index_tree_sha
            and self.tracked_tree_sha == other.tracked_tree_sha
            and self.untracked_files == other.untracked_files
        )


@dataclass
# ID: 20273825-c2bc-4eae-a077-f549d55e9f49
class AssertionResult:
    """One named pass/fail check from the ADR-155 D10 fail-closed assertion model.

    Phase 1 populates only isolation-scoped assertions (the Phase1-Map §
    "Phase 1 test plan" subset); the full chain-scenario assertion set is
    Phase 2's responsibility.
    """

    name: str
    passed: bool
    detail: str = ""


@dataclass
# ID: 32823975-63ac-4914-a048-37ab3a77ec95
class PhaseResult:
    """Outcome shell for one substrate run (clone, compose up/down, cleanup).

    Phase 1 populates ``run_id``/``ok``/``assertions``. Phase 2 adds the
    chain-scenario evidence fields (finding, proposal, consequence, etc.) on
    top of this shell rather than replacing it; Phase 3's CLI renders D12
    evidence from whatever this shell has accumulated by the end of a run.
    """

    run_id: str
    ok: bool
    assertions: list[AssertionResult] = field(default_factory=list)
