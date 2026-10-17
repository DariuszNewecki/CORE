# src/body/governance/law_custody/ledger_watch.py
"""Custody ledger signatures, re-checked only when the ledger changes (#1112).

The State Sensor asks every cycle; ``verify_ledger`` runs ssh-keygen once per
line, so the watch keeps the last result and re-verifies only when the
ledger's (mtime, size) changed *and* its sha256 differs from the one last
verified. A fresh watch (a daemon restart) verifies once.

On a host without the durable ledger (``durable_ledger()`` is None) the check
does not apply. A missing allowed-signers file is reported, never turned into
one failure per line.

CONSTITUTIONAL ALIGNMENT: read-only; ssh-keygen runs only inside
``ledger.verify_ledger``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from pathlib import Path

from body.governance.law_custody.ledger import durable_ledger, verify_ledger


#: Finding subject prefix, one finding per failing line: ``<prefix>::line-<n>``.
LEDGER_SIGNATURE_PREFIX = "governance::ledger_signature"


@dataclass(frozen=True)
# ID: 9408ab04-d523-41cb-bff1-12c744e649b9
class LedgerSignatureState:
    """One look at the ledger's signatures."""

    applies: bool
    ledger: str = ""
    sha256: str = ""
    checked: int = 0
    failures: tuple[tuple[int, str], ...] = field(default_factory=tuple)
    rechecked: bool = False
    problem: str | None = None


# ID: 62afe2dd-1b49-4abc-a879-6ec5fcd62e09
class LedgerSignatureWatch:
    """Remembers the last verification; verifies again only on change."""

    def __init__(self) -> None:
        self._stat: tuple[int, int] | None = None
        self._last: LedgerSignatureState | None = None

    # ID: ea7ecf3c-3343-4efe-b2cf-ebc1d0105965
    def check(self, allowed_signers: Path) -> LedgerSignatureState:
        """The ledger's signature state, re-verified only if the ledger changed."""
        ledger = durable_ledger()
        if ledger is None:
            return LedgerSignatureState(applies=False)
        if not allowed_signers.is_file():
            return LedgerSignatureState(
                applies=True,
                ledger=str(ledger),
                problem=f"allowed signers not found: {allowed_signers}",
            )
        try:
            stat = ledger.stat()
        except OSError as exc:
            return LedgerSignatureState(
                applies=True, ledger=str(ledger), problem=f"ledger unreadable: {exc}"
            )
        key = (stat.st_mtime_ns, stat.st_size)
        if self._last is not None and key == self._stat:
            return _unchanged(self._last)
        try:
            digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
        except OSError as exc:
            return LedgerSignatureState(
                applies=True, ledger=str(ledger), problem=f"ledger unreadable: {exc}"
            )
        self._stat = key
        if self._last is not None and digest == self._last.sha256:
            return _unchanged(self._last)
        checked, failures = verify_ledger(ledger, allowed_signers)
        self._last = LedgerSignatureState(
            applies=True,
            ledger=str(ledger),
            sha256=digest,
            checked=checked,
            failures=tuple(failures),
            rechecked=True,
        )
        return self._last


def _unchanged(last: LedgerSignatureState) -> LedgerSignatureState:
    return replace(last, rechecked=False)


# ID: 87c6224f-593c-4406-9ed3-4100a7cf05d9
def failing_line_findings(state: LedgerSignatureState) -> dict[str, dict]:
    """{subject: finding payload} for every line of *state* that does not verify."""
    return {
        f"{LEDGER_SIGNATURE_PREFIX}::line-{number}": {
            "rule": "governance.ledger_signature",
            "ledger": state.ledger,
            "ledger_sha256": state.sha256,
            "line": number,
            "reason": reason,
            "message": (
                "A custody ledger line does not verify against allowed_signers: "
                "the record of an applied law change cannot be trusted (#1112)."
            ),
        }
        for number, reason in state.failures
    }
