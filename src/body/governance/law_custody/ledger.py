# src/body/governance/law_custody/ledger.py
"""
The custody ledger line (ADR-170 D4, amendment 2026-10-11 (later) item 4).

One line per applied proposal, appended to ``.intent/custody/ledger.jsonl``
in every destination. ``law apply`` writes every field itself -- nothing
the evaluation needs is kept by hand:
- the proposal id and digest; the approver from ``SUDO_USER``;
- the time the report was shown and the time of approval (UTC);
- every path written or removed, with its new sha256; the destinations;
- the files and lines changed;
- the check results, CORE's computed warnings and the proposer's declared
  warnings, both accepted by the approval;
- an SSH signature (``ssh-keygen -Y sign``) over the line without it.

CONSTITUTIONAL ALIGNMENT:
- Builds bytes; writes nothing (``writer`` appends). ``ssh-keygen`` is the
  only process run (governance.dangerous_execution_primitives: justified,
  the D4 signature).
"""

from __future__ import annotations

import difflib
import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from body.governance.law_custody.law_warnings import LawWarning
from body.governance.law_custody.proposal import LawProposal


LEDGER_REL = ".intent/custody/ledger.jsonl"
SIGNING_NAMESPACE = "core-law-ledger"


# ID: a73e310f-d461-48e0-b205-a83a7f5729ae
class LedgerSignError(Exception):
    """The line could not be signed; nothing is written."""


# ID: bfe98803-219f-4f70-a290-967f8857cd3c
def count_changed_lines(old: bytes | None, new: bytes | None) -> int:
    """Lines added plus lines removed between *old* and *new* (text only)."""
    try:
        before = (old or b"").decode("utf-8").splitlines()
        after = (new or b"").decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return 0
    return sum(
        1 for line in difflib.ndiff(before, after) if line.startswith(("+ ", "- "))
    )


# ID: 272479b5-022c-4844-81a6-6c25ee67fb8e
def build_ledger_line(
    *,
    proposal: LawProposal,
    approver: str,
    shown_utc: str,
    approved_utc: str,
    destinations: Sequence[Path],
    checks: Mapping[str, Any],
    computed_warnings: Sequence[LawWarning],
    old: Mapping[str, bytes | None],
) -> dict[str, Any]:
    """The D4 line for *proposal*, without its signature."""
    new: dict[str, bytes | None] = {f.path: f.content for f in proposal.files}
    new.update({path: None for path in proposal.removals})
    return {
        "proposal": proposal.proposal_id,
        "proposal_digest": proposal.digest,
        "approver": approver,
        "shown_utc": shown_utc,
        "approved_utc": approved_utc,
        "paths": {f.path: f.sha256 for f in proposal.files},
        "removed": list(proposal.removals),
        "destinations": [str(d) for d in destinations],
        "files": len(proposal.files) + len(proposal.removals),
        "lines_changed": sum(
            count_changed_lines(old.get(path), content) for path, content in new.items()
        ),
        "checks": dict(checks),
        "warnings_computed": [w.as_dict() for w in computed_warnings],
        "warnings_declared": list(proposal.declared_warnings),
    }


# ID: f228d22e-fd43-42e2-ad31-2f6cc2a63a8e
def canonical_bytes(line: Mapping[str, Any]) -> bytes:
    """The exact bytes that are signed: sorted keys, no spaces, ASCII."""
    return json.dumps(line, sort_keys=True, separators=(",", ":")).encode("ascii")


# ID: d5dbf185-8dbe-4e57-8568-bd2d5f6cca0a
def sign(payload: bytes, key_path: Path, *, timeout: float = 30.0) -> str:
    """Sign *payload* with ``ssh-keygen -Y sign``; return the armored signature."""
    if not key_path.is_file():
        raise LedgerSignError(f"signing key not found: {key_path}")
    try:
        completed = subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(key_path), "-n", SIGNING_NAMESPACE],
            input=payload,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LedgerSignError(f"ssh-keygen could not run: {exc}") from exc
    signature = completed.stdout.decode("ascii", errors="replace")
    if completed.returncode != 0 or "BEGIN SSH SIGNATURE" not in signature:
        raise LedgerSignError(
            "ssh-keygen refused to sign: "
            + completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return signature


# ID: 21a9c4ec-d58e-4263-b240-1798931327ae
def signed_line_bytes(line: Mapping[str, Any], key_path: Path) -> bytes:
    """The ledger line with its signature, as one newline-terminated line."""
    signature = sign(canonical_bytes(line), key_path)
    return canonical_bytes({**line, "signature": signature}) + b"\n"
