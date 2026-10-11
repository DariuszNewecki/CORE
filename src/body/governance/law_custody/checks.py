# src/body/governance/law_custody/checks.py
"""
The data checks ``law apply`` runs on a proposal's scratch tree (ADR-170 D5).

D5 refuses mechanical breakage, and only that:
- ``.intent/`` and ``.specs/`` schema validation (MetaValidator,
  SpecsDocValidator);
- ``architecture.intent.references_resolve`` (reads ``src/`` as text);
- the law loading at all;
- ``.claude/settings.json`` parsing as JSON.

Every one of them reads files as data. The full audit is not run here: it
executes repository code (type checker, CLI discovery), and the custodian
never does (ADR-170 D2; governor ruling 2026-10-11, correcting proposal
0019 item 3). The proposer runs it before asking, and the commit hook again.

The checks run in a child process of the *same* interpreter (``-I``: no
working directory or user site on ``sys.path``), with the scratch tree as
both working directory and ``REPO_PATH``, so the law they read is the
proposal's and nothing else (C-50). The child refuses when the law it
loaded is not the tree's.

CONSTITUTIONAL ALIGNMENT:
- Read-only. The child process is released code reading data; the
  subprocess is the isolation boundary, not repository code execution
  (governance.dangerous_execution_primitives: justified here).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

REFERENCES_RULE_ID = "architecture.intent.references_resolve"
_CHILD_ENTRY = "from cli.admin_cli import app; app()"


# ID: 2dd83490-c414-41ff-b72b-a75be4d545dd
class CheckRunError(Exception):
    """The checks could not be run; this is never read as "no refusals"."""


def _refusal(check: str, message: str) -> dict[str, str]:
    return {"check": check, "message": message}


# ID: f443bc26-25b9-4246-a36f-1e3f0366f557
async def run_data_checks(repo_root: Path) -> dict[str, Any]:
    """Run the D5 refusal checks on *repo_root*; return a JSON-ready report.

    ``refusals`` empty means every check ran and none refused. A check that
    cannot run is itself a refusal ("could not check" is not "clean").
    """
    from mind.governance.audit_context import AuditorContext
    from mind.governance.filtered_audit import run_filtered_audit
    from mind.governance.meta_validator import MetaValidator
    from mind.governance.specs_doc_validator import SpecsDocValidator
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    root = repo_root.resolve()
    refusals: list[dict[str, str]] = []
    checks: dict[str, str] = {}

    try:
        repo = get_intent_repository()
        repo.initialize()
    except Exception as exc:
        refusals.append(_refusal("law_loads", f"the law does not load: {exc}"))
        return {"tree": str(root), "refusals": refusals, "checks": checks}
    law_root = Path(repo.root).resolve()
    if law_root != root / ".intent":
        refusals.append(
            _refusal(
                "law_loads",
                f"loaded law from {law_root}, not from the proposal's tree "
                f"{root / '.intent'}; nothing was checked",
            )
        )
        return {"tree": str(root), "refusals": refusals, "checks": checks}
    checks["law_loads"] = "ok"

    try:
        meta = MetaValidator().validate_all_documents()
        specs = SpecsDocValidator(root).validate_all_documents()
    except Exception as exc:
        refusals.append(_refusal("schema", f"the schema check could not run: {exc}"))
    else:
        for err in [*meta.errors, *specs.errors]:
            refusals.append(_refusal("schema", f"{err.document}: {err.message}"))
        checks["schema"] = (
            f"{meta.documents_valid} intent, {specs.documents_valid} specs valid"
        )

    try:
        context = AuditorContext(
            repo_path=root,
            intent_repository=repo,
            session_provider=None,
            llm_client=None,
            stateless=True,
        )
        context.reload_governance()
        findings, executed, _stats = await run_filtered_audit(
            context, rule_ids=[REFERENCES_RULE_ID]
        )
    except Exception as exc:
        refusals.append(
            _refusal("references", f"{REFERENCES_RULE_ID} could not run: {exc}")
        )
    else:
        if REFERENCES_RULE_ID not in executed:
            refusals.append(_refusal("references", f"{REFERENCES_RULE_ID} did not run"))
        else:
            for finding in findings:
                data = finding.as_dict() if hasattr(finding, "as_dict") else finding
                refusals.append(
                    _refusal(
                        "references",
                        f"{data.get('file_path', '?')}: {data.get('message', data)}",
                    )
                )
            checks["references"] = f"{len(findings)} dangling"

    settings_json = root / ".claude" / "settings.json"
    if settings_json.exists():
        try:
            json.loads(settings_json.read_text(encoding="utf-8"))
            checks["claude_settings"] = "ok"
        except ValueError as exc:
            refusals.append(_refusal("claude_settings", f"not JSON: {exc}"))
    return {"tree": str(root), "refusals": refusals, "checks": checks}


# ID: b2988ed4-41b4-41ce-b471-436ded6f7fc6
def run_checks_in_child(tree: Path, *, timeout: float = 900.0) -> dict[str, Any]:
    """Run ``core-admin law check-tree --json`` on *tree* in a child process.

    Same interpreter, isolated mode, minimal environment, working directory
    and ``REPO_PATH`` both the tree. Raises ``CheckRunError`` when the child
    fails or prints no report.
    """
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", str(tree)),
        "LANG": "C.UTF-8",
        "REPO_PATH": str(tree),
    }
    command = [
        sys.executable,
        "-I",
        "-c",
        _CHILD_ENTRY,
        "law",
        "check-tree",
        "--json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=tree,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckRunError(f"the checks could not run: {exc}") from exc
    report = None
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith("{"):
            try:
                report = json.loads(line)
            except ValueError:
                continue
            break
    if not isinstance(report, dict) or "refusals" not in report:
        tail = (completed.stderr or completed.stdout)[-2000:]
        raise CheckRunError(
            f"the checks printed no report (exit {completed.returncode}): {tail}"
        )
    return report
