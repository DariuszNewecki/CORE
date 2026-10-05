# src/shared/infrastructure/intent/law_state.py

"""Law state: which law an audit evaluated, and how it relates to the law of record (ADR-169 D2).

Two laws are distinguished:

- **law of record** — ``.intent/`` as committed at HEAD;
- **law evaluated** — the live ``.intent/`` the audit actually read.

Both are fingerprinted with one definition, so they are equal exactly when the
live law is the committed law:

    sha256 over sorted "path\\0git-blob-id\\n", for every file under .intent/

The record side comes from ``git ls-tree -r HEAD``; the evaluated side from the
working tree via ``git hash-object`` (no objects written). Ignored files
(``.gitignore``, e.g. ``.intent/keys/``) are outside both.

Relationship: ``MATCH`` (equal), ``DRIFT`` (different; the differing paths are
listed), or ``UNKNOWN`` (the law's location is not a git work tree, or git
failed). UNKNOWN is never treated as MATCH: a precondition that cannot be
evaluated must not pass (governance.no_governance_bypass).

Read-only: runs git through GitService, writes nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from shared.infrastructure.git_service import GitService
from shared.logger import getLogger
from shared.models.audit_models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

LawRelationship = Literal["MATCH", "DRIFT", "UNKNOWN"]

# The finding_type carried by law-drift findings (ADR-169 D2). Listed in
# audit_verdict.yaml ignored_finding_types: drift degrades, it never FAILs.
LAW_DRIFT_FINDING_TYPE = "LAW_DRIFT"
LAW_DRIFT_CHECK_ID = "governance.law_drift"


@dataclass(frozen=True)
# ID: 054f82aa-e96d-4ba6-8c16-bd84ed8e0d5f
class LawState:
    """The evaluated law, the law of record, and their relationship."""

    relationship: LawRelationship
    head_sha: str | None = None
    record_digest: str | None = None
    evaluated_digest: str | None = None
    drift_paths: list[str] = field(default_factory=list)
    reason: str | None = None

    # ID: d16209ba-c642-4746-b2f0-02f087c551d7
    def to_dict(self) -> dict[str, Any]:
        """JSON-ready form, for audit results and the state ledger."""
        return asdict(self)


# ID: 23a4f3fe-2a5d-4c1a-99f7-644bd06e38ad
def law_digest(blobs: dict[str, str]) -> str:
    """Fingerprint a {path: blob-id} map; equal maps give equal digests."""
    payload = "".join(f"{path}\0{blob}\n" for path, blob in sorted(blobs.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ID: c92f6298-6e7b-4eed-84b4-22d56b617b3e
def observe_law_state(intent_root: Path) -> LawState:
    """Compare the live law under intent_root with the law committed at HEAD."""
    root = Path(intent_root).resolve()
    top = GitService.toplevel_of(root) if root.is_dir() else None
    if top is None:
        return LawState(
            relationship="UNKNOWN",
            reason=f"{root} is not inside a git work tree",
        )
    rel = root.relative_to(top).as_posix()
    git = GitService(top)
    try:
        head_sha = git.get_current_commit()
        record = git.ls_tree_blobs("HEAD", rel)
        evaluated = git.hash_working_paths(rel)
        record_digest = law_digest(record)
        evaluated_digest = law_digest(evaluated)
        drift_paths = (
            git.changed_paths(rel) if record_digest != evaluated_digest else []
        )
    except RuntimeError as exc:
        logger.warning("law state could not be observed for %s: %s", root, exc)
        return LawState(relationship="UNKNOWN", reason=f"git failed: {exc}")

    return LawState(
        relationship="MATCH" if record_digest == evaluated_digest else "DRIFT",
        head_sha=head_sha,
        record_digest=record_digest,
        evaluated_digest=evaluated_digest,
        drift_paths=drift_paths,
    )


# ID: f3d4eb75-0209-4398-bb20-0cc866d2a180
def law_drift_findings(state: LawState) -> list[AuditFinding]:
    """Findings naming why the evaluated law is not the law of record.

    One finding per differing path (DRIFT), or one finding when the relation
    is UNKNOWN. Severity MEDIUM with finding_type LAW_DRIFT: drift makes the
    verdict DEGRADED via the ``law_drift`` precondition and never FAIL.
    """
    if state.relationship == "MATCH":
        return []
    context = {
        "finding_type": LAW_DRIFT_FINDING_TYPE,
        "relationship": state.relationship,
        "head_sha": state.head_sha,
        "law_record_digest": state.record_digest,
        "law_evaluated_digest": state.evaluated_digest,
    }
    if state.relationship == "UNKNOWN":
        return [
            AuditFinding(
                check_id=LAW_DRIFT_CHECK_ID,
                severity=AuditSeverity.MEDIUM,
                message=(
                    "Cannot establish that the law evaluated is the law of "
                    f"record: {state.reason}. Verdict cannot be PASS."
                ),
                file_path=".intent",
                context=context,
            )
        ]
    paths = state.drift_paths or [".intent"]
    head = (state.head_sha or "")[:12]
    return [
        AuditFinding(
            check_id=LAW_DRIFT_CHECK_ID,
            severity=AuditSeverity.MEDIUM,
            message=(
                f"{path} differs from the law of record at {head}: the audit "
                "evaluated uncommitted law. Commit or revert it; until then the "
                "verdict is DEGRADED, never PASS."
            ),
            file_path=path,
            context=context,
        )
        for path in paths
    ]
