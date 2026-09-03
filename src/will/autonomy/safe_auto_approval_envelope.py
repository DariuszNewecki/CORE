# src/will/autonomy/safe_auto_approval_envelope.py
"""
Safe auto-approval authorization boundary (#853).

Independently governed action-and-path envelope for
risk_classification.safe_auto_approval, enforced centrally in
ProposalStateManager.approve(). Distinct from -- and never inferred from --
impact_level: safe classification in action_risk.yaml, and never trusted
from a proposal's self-declared ProposalScope: every action's actual
target path is validated here, then cross-checked against the proposal's
declared scope.files for consistency.

Governed by the safe_auto_approval_envelope section of
.intent/enforcement/config/action_risk.yaml (loaded via
shared.infrastructure.intent.action_risk.load_safe_auto_approval_envelope).

Fail-closed by construction: an envelope-load failure, an unlisted action,
a flow reference, a missing/malformed/absolute/traversal/out-of-envelope
path, and an action/scope inconsistency all deny -- never silently
authorize. Denial does NOT delete or roll back the proposal; callers keep
it in DRAFT for principal.governor review (governor ruling 6), which is
not bound by this envelope (governor ruling 7).

LAYER: will/autonomy — no filesystem access, no DB access. Pure validation
over already-loaded action/scope data.
"""

from __future__ import annotations

from typing import Any

from shared.exceptions import CoreError
from shared.infrastructure.intent.action_risk import load_safe_auto_approval_envelope
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 9abfb360-d633-44b9-bc2c-083ccd471d42
class SafeAutoApprovalDeniedError(CoreError):
    """A proposal is not eligible for risk_classification.safe_auto_approval.

    Distinct from ProposalNotFoundError (row not found) and the plain
    ValueError raised for a malformed approval_authority value -- this is
    specifically the envelope's own denial. Callers (the autonomous
    proposal creators) MUST catch this and commit the already-created
    proposal in DRAFT rather than treat it as a persistence failure; the
    proposal remains available for principal.governor review.
    """


# ID: 3a05c487-5eb6-46e9-8fa3-4399ed65405d
def validate_envelope(actions: list[dict[str, Any]], scope: dict[str, Any]) -> None:
    """Validate a proposal's actions/scope against the safe auto-approval envelope.

    Raises SafeAutoApprovalDeniedError on the first violation found:
    envelope unavailable, an unlisted action, a flow reference, a missing
    target, a malformed/absolute/traversal/out-of-envelope path, or an
    action/scope inconsistency (the set of files actions actually target
    must equal the proposal's declared scope.files exactly). Returns None
    (no exception) only when every check passes.
    """
    envelope = load_safe_auto_approval_envelope()
    if envelope.get("_error"):
        raise SafeAutoApprovalDeniedError(
            "safe_auto_approval_envelope could not be loaded "
            f"({envelope.get('reason', 'unknown')}) — denying safe "
            "auto-approval; envelope failures must never silently authorize."
        )

    authorized_actions: frozenset[str] = envelope["authorized_actions"]
    path_prefixes: tuple[str, ...] = envelope["authorized_path_prefixes"]
    extensions: tuple[str, ...] = envelope["authorized_extensions"]

    if not actions:
        raise SafeAutoApprovalDeniedError("proposal declares no actions")

    action_target_files: set[str] = set()
    for action in actions:
        action_id = action.get("action_id")
        flow_id = action.get("flow_id")
        if flow_id is not None or action_id is None:
            raise SafeAutoApprovalDeniedError(
                f"flow {flow_id!r} is not authorized for safe auto-approval "
                "— no flow is initially authorized, including test-"
                "generation flows"
            )
        if action_id not in authorized_actions:
            raise SafeAutoApprovalDeniedError(
                f"action {action_id!r} is not in the safe auto-approval "
                f"envelope (authorized: {sorted(authorized_actions)})"
            )
        parameters = action.get("parameters") or {}
        file_path = parameters.get("file_path")
        if not file_path or not isinstance(file_path, str):
            raise SafeAutoApprovalDeniedError(
                f"action {action_id!r} declares no target file_path — "
                "safe auto-approval requires a concrete target"
            )
        _validate_target_path(file_path, path_prefixes, extensions)
        action_target_files.add(file_path)

    scope_files = set(scope.get("files") or [])
    if action_target_files != scope_files:
        raise SafeAutoApprovalDeniedError(
            "action targets and declared scope.files are inconsistent "
            f"(action targets: {sorted(action_target_files)}, "
            f"scope.files: {sorted(scope_files)})"
        )


def _validate_target_path(
    file_path: str, path_prefixes: tuple[str, ...], extensions: tuple[str, ...]
) -> None:
    """Reject anything but a clean, repo-relative, in-envelope path.

    Lexical only — no filesystem access, no repo_root dependency. Rejects
    absolute paths (POSIX and Windows-drive shapes) and backslash
    separators before checking for '.'/'..' traversal segments, then
    checks the envelope's path-prefix/extension allowlist.
    """
    if file_path.startswith("/") or file_path.startswith("~"):
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} is absolute or home-relative — "
            "only repository-relative paths are authorized"
        )
    if "\\" in file_path:
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} contains a backslash — repository-"
            "relative paths use forward slashes only"
        )
    if len(file_path) >= 2 and file_path[1] == ":":
        # Windows drive-letter shape (C:\..., C:/...) — defense in depth.
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} looks like a Windows absolute path"
        )
    segments = file_path.split("/")
    if "" in segments or "." in segments or ".." in segments:
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} is malformed or contains a traversal segment"
        )
    if not any(file_path.startswith(prefix) for prefix in path_prefixes):
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} is outside the authorized "
            f"envelope ({', '.join(path_prefixes)})"
        )
    if not any(file_path.endswith(ext) for ext in extensions):
        raise SafeAutoApprovalDeniedError(
            f"target path {file_path!r} does not have an authorized "
            f"extension ({', '.join(extensions)})"
        )
