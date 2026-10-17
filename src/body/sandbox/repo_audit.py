# src/body/sandbox/repo_audit.py
"""
Run CORE's audit over a candidate tree in the sandbox (external review F1).

``assisted.validate_diff`` judges a patch with the patched tree's own engine
(ADR-141 D3), which means importing and running candidate code. That code
must not run as the services account: it would read what ``core`` reads
(the database credential among it, and with it the approval records
``assisted.apply_diff`` trusts) and write outside its worktree. So the audit
is a sandbox job (``kind: audit``), run like every other piece of repository
code (ADR-132 D10.10).

Fail closed: outside ``service`` mode the audit is not started at all
(``local`` mode would run candidate code as the caller); an audit that did
not run, failed, or reports another isolation yields no result, only the
reason, and the caller never reads that as a pass.

CONSTITUTIONAL ALIGNMENT:
- Body: executes only through the sandbox client.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from body.sandbox.client import SandboxRequest, run_repo_code
from body.sandbox.models import SandboxResult
from body.sandbox.repo_tests import repo_include, sandbox_mode
from shared.infrastructure.intent.law_roots import intent_root_for, specs_root_for


# The only isolation under which candidate code's audit result is evidence.
REQUIRED_ISOLATION = "service"
AUDIT_TIMEOUT_SEC = 540


# ID: 47cfeb2f-043d-48f6-bbd9-b02ea4dccddc
async def run_audit_in_sandbox(
    tree: Path,
    *,
    rule_ids: Sequence[str] = (),
    check_files: Sequence[str] = (),
    timeout_sec: int = AUDIT_TIMEOUT_SEC,
) -> SandboxResult:
    """Audit *tree* in the sandbox: *rule_ids* only, or (none given) the full
    stateless audit plus the Class B rules on *check_files*.

    The copy goes to the bound repository's inbox, the only one the service
    reads, whatever *tree* is.
    """
    from shared.infrastructure.bootstrap_registry import BootstrapRegistry

    mode = sandbox_mode()
    if mode != REQUIRED_ISOLATION:
        return SandboxResult.not_run(
            mode,
            f"the audit runs candidate code and is started only in "
            f"{REQUIRED_ISOLATION!r} sandbox mode (CORE_SANDBOX_MODE={mode!r})",
        )
    bound = Path(BootstrapRegistry.get_repo_path())
    tree = Path(tree)
    law = tuple(
        root for root in (intent_root_for(tree), specs_root_for(tree)) if root.is_dir()
    )
    return await run_repo_code(
        SandboxRequest(
            tree=tree,
            targets=tuple(check_files),
            timeout_sec=timeout_sec,
            include=repo_include(tree),
            law=law,
            audit=True,
            audit_rules=tuple(rule_ids),
        ),
        repo_root=bound,
        mode=mode,
    )


# ID: 7a9e4f35-c644-4664-ab42-87fa61ce7d74
def isolated_audit(result: SandboxResult) -> tuple[dict[str, Any] | None, str | None]:
    """(the audit's result, None) when it ran to the end inside the sandbox
    service; otherwise (None, why it is not evidence)."""
    if result.isolation != REQUIRED_ISOLATION:
        return None, (
            f"the audit ran with isolation {result.isolation!r}, not "
            f"{REQUIRED_ISOLATION!r}: candidate code ran without the sandbox "
            "service's walls, so its result is not evidence (F1)"
        )
    if not result.ok:
        return (
            None,
            f"the sandboxed audit did not finish: {result.status}: {result.reason}",
        )
    return result.audit, None
