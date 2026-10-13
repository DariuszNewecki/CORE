# src/body/governance/law_custody/writer.py
"""
The only code that writes governed text (ADR-170 D2, D3 step 3).

IntentGuard refuses every write under ``.intent/`` for every service, and
that invariant is unchanged: this module does not go through FileHandler
at all. It is a separate, named write surface (excluded by name from
``governance.mutation_surface.filehandler_required`` and
``governance.logic_mutation.governed``), and it refuses to write unless
the process runs as the custodian account, ``core-law``.

The account check is a tripwire, not the lock. The lock is the operating
system: in Stage 1 only ``core-law`` can write governed text at all.

What it writes:
- the scratch tree the data checks run on (outside every destination);
- the proposal's bytes, to every destination, each file replaced
  atomically; on any failure it stops and reports which destination holds
  which bytes, and no ledger line is written (amendment 2026-10-11 item 2);
- the signed ledger line, appended to every destination.

CONSTITUTIONAL ALIGNMENT:
- Writes only governed text and its own scratch tree; never runs git or
  repository code.
"""

from __future__ import annotations

import os
import pwd
import shutil
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from body.governance.law_custody.ledger import LEDGER_REL, durable_ledger
from body.governance.law_custody.proposal import LawProposal


CUSTODIAN_ACCOUNT = "core-law"
# What release law holds (ADR-132 D10.13); every destination after the first.
RELEASE_LAW_TOPS = frozenset({".intent", ".specs"})
# The scratch tree: governed text is copied (the proposal is applied on top of
# the copy); every other top-level entry is linked read-only, because the law
# references files anywhere in the repository (references_resolve: src/,
# infra/, tests/ ...). Nothing in it is executed. Runtime state, secrets and
# caches are left out.
SCRATCH_COPIED = (
    ".intent",
    ".specs",
    "CLAUDE.md",
    ".claude/settings.json",
    ".claude/hooks",
)
SCRATCH_NOT_LINKED = frozenset(
    {
        ".git",
        ".claude",
        ".venv",
        "var",
        ".secrets",
        "dist",
        "work",
        "reports",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".coverage",
    }
)


# ID: ca378ee5-8863-43a4-8828-b2536a7ca3dc
class CustodyError(Exception):
    """Refused before anything was written."""


@dataclass
# ID: 3fbfe8a0-6358-49db-9de7-51c4aae14860
class DestinationOutcome:
    """What one destination holds after a write attempt."""

    root: Path
    written: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    failed: str | None = None


# ID: 29c87a2a-89da-4c31-88fc-07032c666916
def current_account() -> str:
    """The effective account name of this process."""
    return pwd.getpwuid(os.geteuid()).pw_name


# ID: 28d591ed-fdc8-4cfd-985a-2226ad34c09f
def require_custodian(
    env: Mapping[str, str], *, custodian: str = CUSTODIAN_ACCOUNT
) -> str:
    """Refuse unless running as *custodian* under sudo; return the approver.

    The approver is ``SUDO_USER`` (ADR-170 D4): sudo sets it and the caller
    cannot supply it. A run as the custodian without sudo has no approver
    and is refused.
    """
    account = current_account()
    if account != custodian:
        raise CustodyError(
            f"law apply runs only as {custodian} (this process runs as {account})"
        )
    approver = env.get("SUDO_USER", "").strip()
    if not approver or approver == custodian:
        raise CustodyError(
            "no approver: run it as `sudo -u core-law ... law apply <id>` from "
            "the governor's own account"
        )
    return approver


def _safe_target(root: Path, rel: str) -> Path:
    """``root/rel``, refusing a path that leaves *root* or passes a symlink."""
    target = root / rel
    current = root
    for part in Path(rel).parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise OSError(f"symlinked directory on the path: {current}")
    if target.is_symlink():
        raise OSError(f"target is a symlink: {target}")
    resolved_root = root.resolve()
    if not target.resolve().is_relative_to(resolved_root):
        raise OSError(f"{rel} resolves outside {root}")
    return target


def _replace_atomically(target: Path, content: bytes) -> None:
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if (
        target.is_file()
        and not os.access(target.parent, os.W_OK)
        and os.access(target, os.W_OK)
    ):
        # The repository root is root-owned and sticky (ADR-170 D2): core-law
        # owns CLAUDE.md but cannot create a temp file beside it, so the file
        # it owns is rewritten in place.
        fd = os.open(target, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return
    temp = target.parent / f".{target.name}.law-apply.tmp"
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink()


# ID: 4c0af57a-5c20-4082-ab09-f9f0c1607176
def build_scratch_tree(
    source: Path,
    scratch_parent: Path,
    proposal: LawProposal,
    *,
    custodian: str = CUSTODIAN_ACCOUNT,
) -> Path:
    """Copy governed text, link the rest of *source*, apply *proposal* on top.

    Returns the scratch tree. The caller removes it (``remove_scratch_tree``).
    """
    if current_account() != custodian:
        raise CustodyError(f"the scratch tree is built only as {custodian}")
    tree = scratch_parent / f"law-apply-{proposal.proposal_id}-{os.getpid()}"
    if tree.exists():
        shutil.rmtree(tree)
    tree.mkdir(mode=0o755, parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for rel in SCRATCH_COPIED:
        origin = source / rel
        target = tree / rel
        target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        if origin.is_dir() and not origin.is_symlink():
            shutil.copytree(origin, target, symlinks=True, ignore=ignore)
        elif origin.is_file() and not origin.is_symlink():
            shutil.copy2(origin, target)
    governed_roots = {Path(rel).parts[0] for rel in SCRATCH_COPIED}
    for entry in sorted(source.iterdir()):
        name = entry.name
        if (
            name in governed_roots
            or name in SCRATCH_NOT_LINKED
            or name.startswith(".env")
        ):
            continue
        (tree / name).symlink_to(entry)
    for proposed in proposal.files:
        _replace_atomically(_safe_target(tree, proposed.path), proposed.content)
    for rel in proposal.removals:
        target = _safe_target(tree, rel)
        if target.exists():
            target.unlink()
    return tree


# ID: 0b7edbf8-772f-403d-9c33-8f1cd75791e1
def remove_scratch_tree(tree: Path) -> None:
    """Remove a scratch tree made by ``build_scratch_tree``."""
    if tree.name.startswith("law-apply-") and tree.is_dir() and not tree.is_symlink():
        shutil.rmtree(tree)


# ID: f5cbd1e3-47de-4ff6-a322-811980f14176
def write_destinations(
    destinations: Sequence[Path],
    proposal: LawProposal,
    *,
    custodian: str = CUSTODIAN_ACCOUNT,
) -> list[DestinationOutcome]:
    """Write the proposal's in-memory bytes to every destination, in order.

    The first destination is the development tree and receives every path.
    The others are release law (ADR-132 D10.13): they hold only ``.intent/``
    and ``.specs/``, so ``CLAUDE.md`` and ``.claude/`` are not theirs.

    Stops at the first failure; the outcomes say which destination holds
    which bytes. No ledger line is written here.
    """
    if current_account() != custodian:
        raise CustodyError(f"governed text is written only as {custodian}")
    outcomes: list[DestinationOutcome] = []
    for index, root in enumerate(destinations):
        outcome = DestinationOutcome(root=root)
        outcomes.append(outcome)
        release = index > 0

        try:
            if not root.is_dir() or root.is_symlink():
                raise OSError(f"destination is not a directory: {root}")
            for proposed in proposal.files:
                if release and Path(proposed.path).parts[0] not in RELEASE_LAW_TOPS:
                    continue
                _replace_atomically(_safe_target(root, proposed.path), proposed.content)
                outcome.written.append(proposed.path)
            for rel in proposal.removals:
                if release and Path(rel).parts[0] not in RELEASE_LAW_TOPS:
                    continue
                target = _safe_target(root, rel)
                if target.exists():
                    if not stat.S_ISREG(os.lstat(target).st_mode):
                        raise OSError(f"not a regular file: {target}")
                    target.unlink()
                outcome.removed.append(rel)
        except OSError as exc:
            outcome.failed = str(exc)
            break
    return outcomes


# ID: 20903492-960b-4a1c-bebf-91918de74115
def append_ledger(
    destinations: Sequence[Path], line: bytes, *, custodian: str = CUSTODIAN_ACCOUNT
) -> None:
    """Append the signed *line* to the durable ledger when the host has one,
    otherwise to the ledger in every destination."""
    if current_account() != custodian:
        raise CustodyError(f"the ledger is written only as {custodian}")
    if not line.endswith(b"\n") or line.count(b"\n") != 1:
        raise CustodyError("a ledger entry is exactly one line")
    durable = durable_ledger()
    if durable is not None:
        _append_line(durable, line)
        return
    for root in destinations:
        ledger = _safe_target(root, LEDGER_REL)
        ledger.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        _append_line(ledger, line)


def _append_line(ledger: Path, line: bytes) -> None:
    fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
