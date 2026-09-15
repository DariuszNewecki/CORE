"""Materializes the neutral external-target fixture as a real disposable
Git repository (Unit C, Governor-authorized external-target safety
package; Governor ruling 2026-09-06, recorded in
.specs/decisions/ADR-159-autonomy-thesis-acceptance-boundary.md Notes).

Assembles a target-local ``.intent/`` from two layers, per the Governor's
instruction, via the production builder
``shared.infrastructure.intent.target_intent_assembly.assemble_target_intent``
(#894 D-b: one builder for the fixture, the external-run command and the
future offline onboard):

1. the existing bundled machinery floor (``src/shared/_machinery_floor``,
   copied verbatim -- the same mechanism Units A and B's own tests already
   use for a disposable external repository);
2. the smallest reviewable fixture-owned overlay carrying the ratified
   authority (``intent_overlay/``, a tree mirroring ``.intent/`` layout,
   copied additively -- an overlay path that is also a floor path is
   refused, ADR-159 Note 2026-09-15 Condition 1): one new rule document at
   ``rules/code/purity.json``, the ``safe_auto_approval_envelope`` in its
   own overlay-owned file ``enforcement/config/safe_auto_approval_envelope.yaml``
   (it was merged into the floor's ``action_risk.yaml`` until #894
   Condition 1 forbade modifying any floor file),
   ``rules/ai/capability_taxonomy_governance.json`` copied byte-identical
   from CORE's own tree (2026-09-15, #894 seeding unit: the mandatory policy
   dependency of ``project.cognitive_roles`` and ``seed.external_run_resources``,
   which ActionExecutor validates against the BOUND copy's ``.intent/`` --
   the same shape as the ``proposal_lifecycle`` dependency below),
   ``workflows/definitions/code_modification.yaml`` copied byte-identical from
   CORE's own tree (2026-09-15, #894 seeding unit: the workflow definition
   ``WorkflowOrchestrator.execute_goal`` resolves through the BOUND
   IntentRepository -- absent from the floor, so an external run stopped at
   "Workflow not found"; overlaid here as configuration, with the open
   question of whether workflow definitions are floor content),
   the six ``phases/*.yaml`` constitutional phase declarations copied
   byte-identical from CORE's own tree (2026-09-15, #894 seeding unit:
   ``PhaseRegistry`` loads phases through the BOUND IntentRepository; the
   floor ships none, so the seeded live run crashed at
   ``PhaseRegistry.get("interpret")`` -- same floor-vs-overlay question),
   one ``workers/proposal_consumer_worker.yaml`` declaration (Governor
   ruling 2026-09-07) giving the worker constitutional standing scoped
   exactly to ``package/example.py`` -- it does not touch the envelope
   above, which remains the sole source of what ``fix.format`` may do --
   and one ``rules/will/proposal_lifecycle.json`` policy document
   (Governor ruling 2026-09-07, second), copied byte-identical from
   CORE's own ``.intent/rules/will/proposal_lifecycle.json``: the
   mandatory policy dependency of the production ``claim.proposal``
   atomic action, which ``ProposalExecutor`` invokes internally for any
   proposal regardless of the action it carries. Its absence is why
   ``claim.proposal`` failed its own policy validation on the prior live
   attempt -- adding it does not widen the safe-auto-approval envelope
   past ``fix.format`` on ``package/*.py``.
   ``rules/code/imports.json`` copied byte-identical from CORE's own tree
   (Governor ruling 2026-09-15: policies belong in the overlay, never the
   floor -- ADR-119 excludes ``rules/`` from the floor -- and only the
   mechanically enumerated policy dependencies of the exercised audit
   path, never CORE's rules wholesale): the declared policy of
   ``check.imports``, which ``canary_validation`` executes for a
   ``code_modification`` run; ``test_external_run_audit_path`` derives the
   required set from the executed actions' registrations, so a widened
   path fails there before it fails live.

Performs no side effects against CORE itself: every write lands under the
caller-supplied *dest* (a pytest ``tmp_path``), never inside this checkout.
Deliberately a small, single-purpose helper rather than a general fixture
framework -- one function, one dataclass, no configurability beyond *dest*.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from shared.infrastructure.intent.target_intent_assembly import (
    assemble_target_intent,
)


_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parents[2]
MACHINERY_FLOOR = REPO_ROOT / "src" / "shared" / "_machinery_floor"
TEMPLATE_DIR = _HERE / "template"
OVERLAY_DIR = _HERE / "intent_overlay"


@dataclass(frozen=True)
# ID: 1f2a3b4c-5d6e-7f80-9a1b-2c3d4e5f6a7b
class MaterializedTarget:
    """A materialized, git-committed copy of the external-target fixture."""

    root: Path
    intent_root: Path
    baseline_commit: str
    baseline_tree: str


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _assemble_intent(target_root: Path) -> Path:
    """Floor + fixture overlay, via the production builder (#894 D-b)."""
    assembled = assemble_target_intent(target_root / ".intent", OVERLAY_DIR)
    return assembled.intent_root


# ID: 2a3b4c5d-6e7f-8091-a2b3-c4d5e6f7a8b9
def materialize_external_target(dest: Path) -> MaterializedTarget:
    """Materialize the fixture at *dest* as a committed, disposable Git repo.

    *dest* must not already exist. Copies the committed ``template/`` tree
    (production package, native test, out-of-envelope script), assembles
    ``.intent/`` per the module docstring, then initializes Git with a
    local test identity and creates exactly one baseline commit. Never
    creates a remote. Never touches CORE's own tree or the committed
    ``template/``/``intent_overlay/`` sources (only reads from them).
    """
    dest.mkdir(parents=True, exist_ok=False)

    shutil.copytree(
        TEMPLATE_DIR,
        dest,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    _assemble_intent(dest)

    _git(["init"], dest)
    _git(["config", "user.email", "test@external-target-fixture.local"], dest)
    _git(["config", "user.name", "External Target Fixture"], dest)
    _git(["config", "commit.gpgsign", "false"], dest)
    _git(["add", "-A"], dest)
    _git(["commit", "-m", "Unit C fixture baseline"], dest)

    baseline_commit = _git(["rev-parse", "HEAD"], dest)
    baseline_tree = _git(["write-tree"], dest)

    return MaterializedTarget(
        root=dest,
        intent_root=dest / ".intent",
        baseline_commit=baseline_commit,
        baseline_tree=baseline_tree,
    )


def git_snapshot(repo: Path) -> tuple[str, str, str]:
    """Return (HEAD sha, tree hash, porcelain status) for *repo*."""
    head = _git(["rev-parse", "HEAD"], repo)
    tree = _git(["write-tree"], repo)
    status = _git(["status", "--porcelain"], repo)
    return head, tree, status
