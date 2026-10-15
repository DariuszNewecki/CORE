# src/body/governance/law_custody/ledger.py
"""
The custody ledger line (ADR-170 D4, amendment 2026-10-11 (later) item 4).

One line per applied proposal. On a host that has the durable custody
ledger (``/opt/core/custody/ledger.jsonl``, outside every working tree and
outside the law tree a deploy rewrites) the line goes there and only there;
otherwise it is appended to ``.intent/custody/ledger.jsonl`` in every
destination. ``law apply`` writes every field itself -- nothing
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
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from body.governance.law_custody.law_warnings import LawWarning
from body.governance.law_custody.proposal import LawProposal


LEDGER_REL = ".intent/custody/ledger.jsonl"
SIGNING_NAMESPACE = "core-law-ledger"
# The host's durable ledger: created by the host step, owned by core-law.
# A deploy writes law into the development tree and the release law; neither
# is a place a record may live (a checkout reset or a law resync drops it).
CUSTODY_LEDGER = Path("/opt/core/custody/ledger.jsonl")
CUSTODY_LEDGER_ENV = "CORE_CUSTODY_LEDGER"


# ID: 45d4188e-91eb-4788-badd-a18547eaa7d5
def durable_ledger() -> Path | None:
    """The host's durable custody ledger, or None when the host has none.

    ``CORE_CUSTODY_LEDGER`` overrides the location (tests); the ledger counts
    as present when its directory exists.
    """
    path = Path(os.environ.get(CUSTODY_LEDGER_ENV) or CUSTODY_LEDGER)
    return path if path.parent.is_dir() else None


# ID: 6bf357ca-8a11-4b6a-b5ef-cbb1105fbb57
def ledger_file(repo_root: Path) -> Path:
    """Where the ledger of record is read: the durable ledger when the host
    has one, otherwise the repository's own ``.intent/custody/ledger.jsonl``."""
    return durable_ledger() or Path(repo_root) / LEDGER_REL


# ID: a73e310f-d461-48e0-b205-a83a7f5729ae
class LedgerSignError(Exception):
    """The line could not be signed; nothing is written."""


# ID: 6dc8b10c-1764-4f0f-b68e-36c313853195
def recorded_hashes(repo_root: Path) -> dict[str, set[str]]:
    """Every sha256 the custody ledger records for each path (#966), and
    ``REMOVED`` for a path a line removed.

    Read from the ledger ``law apply`` appends to. Unreadable lines are
    skipped: the set says what is known to be recorded, nothing more.
    """
    recorded: dict[str, set[str]] = {}
    try:
        text = ledger_file(repo_root).read_text(encoding="utf-8")
    except OSError:
        return recorded
    for raw in text.splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        for path, digest in (entry.get("paths") or {}).items():
            recorded.setdefault(path, set()).add(str(digest))
        for path in entry.get("removed") or []:
            recorded.setdefault(path, set()).add(REMOVED)
    return recorded


#: The marker recorded_hashes uses for a path a ledger line removed.
REMOVED = "removed"


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
