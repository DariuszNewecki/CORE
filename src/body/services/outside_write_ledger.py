# src/body/services/outside_write_ledger.py
"""
Outside-write ledger — every write CORE makes outside its own repository is
recorded (ADR-169 D5).

Until ADR-166's external-target writer exists, the sanctioned out-of-repo
write sites append their entries directly: ``project onboard`` (initialize +
promote, cli.logic.byor), ``project adopt-pack`` (byor
deliver_external_intent_files), ``project scout`` (cli.logic.scout) and
``project new`` (cli.logic.project_scaffold).

Usage at a write site::

    log = OutsideWriteLog(target_root, produced_by="project.new")
    await log.require_ledger()   # BEFORE the first write; refuses if unreachable
    ...write dest...
    log.wrote(dest)          # sha256 of the bytes now on disk
    ...delete dest...
    log.deleted(dest)
    await log.flush()        # one INSERT batch into core.outside_writes

Each entry: target root, target-relative path, operation (write / delete),
sha256 of the written bytes, producer. No content and no secret material is
recorded — only the hash.

The ledger is a precondition, not best effort (governor ruling on #953,
option A with one boundary):

- ``require_ledger`` runs before the first write. When a CORE database is
  configured but the ledger cannot be reached, it raises
  ``OutsideWriteLedgerUnavailable`` and nothing is written.
- If the ledger is lost after the writes (between the check and ``flush``),
  ``flush`` keeps every entry on the log and raises ``OutsideWritesUnrecorded``
  naming each path; the command fails instead of reporting success.
- The boundary: an installation with no CORE database configured at all
  (a standalone ``pip install`` scaffolding an adopter project) has no CORE
  state to record. The writes proceed and the log says plainly, naming the
  paths, that no record was kept and why.

Constitutional standing: body/services. Reads the files it hashes; writes
only to the database. No LLM calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import text

from shared.infrastructure.database.session_manager import database_is_configured
from shared.logger import getLogger
from shared.workers.blackboard_publisher import _sanitize_payload


logger = getLogger(__name__)

OutsideOperation = Literal["write", "delete"]


# ID: 9c285cf7-64c7-41f3-aa9f-08f21e454cce
class OutsideWriteLedgerError(RuntimeError):
    """The outside-write ledger could not do its job (ADR-169 D5, #953)."""


# ID: 7fc89240-763d-46be-8da0-87993d19f244
class OutsideWriteLedgerUnavailable(OutsideWriteLedgerError):
    """The ledger is unreachable before any write; the write is refused."""


# ID: 0c2f5e68-46f7-4b1e-a7f2-ae4394ad2924
class OutsideWritesUnrecorded(OutsideWriteLedgerError):
    """Writes happened but could not be recorded; entries stay on the log."""


@dataclass(frozen=True)
# ID: d58468f6-b527-460b-8b64-01542e62a7df
class OutsideWrite:
    """One recorded out-of-repo write."""

    path: str
    operation: OutsideOperation
    content_hash: str | None


@dataclass
# ID: 93d6bd2d-9f17-4b9b-9680-daa621099963
class OutsideWriteLog:
    """Collects the out-of-repo writes of one operation, then records them."""

    target_root: Path
    produced_by: str
    proposal_id: str | None = None
    entries: list[OutsideWrite] = field(default_factory=list)

    def _rel(self, dest: Path) -> str:
        dest = Path(dest)
        try:
            return (
                dest.resolve().relative_to(Path(self.target_root).resolve()).as_posix()
            )
        except ValueError:
            return dest.resolve().as_posix()

    # ID: bf1d4e19-1f6a-4a9e-85c8-6c1564b86242
    def wrote(self, dest: Path) -> None:
        """Record that ``dest`` was written; hashes the bytes now on disk."""
        try:
            digest: str | None = hashlib.sha256(Path(dest).read_bytes()).hexdigest()
        except OSError:
            digest = None
        self.entries.append(OutsideWrite(self._rel(dest), "write", digest))

    # ID: 5c38c648-7d30-400c-88e6-04e800babd93
    def deleted(self, dest: Path) -> None:
        """Record that ``dest`` was deleted."""
        self.entries.append(OutsideWrite(self._rel(dest), "delete", None))

    # ID: 3ed3e113-d69e-4bcf-b379-8c48bf8654e6
    async def require_ledger(self) -> None:
        """Refuse before any write unless core.outside_writes is reachable.

        Raises OutsideWriteLedgerUnavailable naming the producer and target.
        With no CORE database configured (standalone install), there is no
        ledger to require: the writes proceed and are reported unrecorded.
        """
        if not database_is_configured():
            logger.warning(
                "outside-write ledger: no CORE database is configured "
                "(standalone install); %s will write under %s WITHOUT a "
                "ledger record (ADR-169 D5 applies to installations with a "
                "ledger)",
                self.produced_by,
                Path(self.target_root).resolve().as_posix(),
            )
            return
        try:
            from body.services.service_registry import ServiceRegistry

            async with ServiceRegistry.session() as session:
                await session.execute(text("SELECT 1 FROM core.outside_writes LIMIT 0"))
        except Exception as exc:
            raise OutsideWriteLedgerUnavailable(
                f"outside-write ledger unreachable; {self.produced_by} refused "
                f"to write under {Path(self.target_root).resolve().as_posix()} "
                f"-- every write CORE makes outside its repository must be "
                f"recorded (ADR-169 D5): {exc}"
            ) from exc

    # ID: 808d86b9-dbaa-4b2c-a57a-ed547e884e24
    async def flush(self) -> None:
        """Append every collected entry to core.outside_writes and clear them.

        Raises OutsideWritesUnrecorded, naming every path, when the ledger
        cannot be reached; the entries stay on the log, never dropped. With no
        CORE database configured, logs the unrecorded paths and clears them.
        """
        if not self.entries:
            return
        entries = list(self.entries)
        root = Path(self.target_root).resolve().as_posix()
        if not database_is_configured():
            logger.warning(
                "outside-write ledger: %d write(s) by %s under %s not recorded "
                "-- no CORE database is configured (standalone install): %s",
                len(entries),
                self.produced_by,
                root,
                ", ".join(e.path for e in entries),
            )
            self.entries.clear()
            return
        try:
            from body.services.service_registry import ServiceRegistry

            async with ServiceRegistry.session() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO core.outside_writes
                            (target_root, path, operation, content_hash,
                             produced_by, proposal_id)
                        VALUES
                            (:target_root, :path, :operation, :content_hash,
                             :produced_by, :proposal_id)
                        """
                    ),
                    [
                        {
                            # The core DB is SQL_ASCII (#359).
                            "target_root": _sanitize_payload(root),
                            "path": _sanitize_payload(e.path),
                            "operation": e.operation,
                            "content_hash": e.content_hash,
                            "produced_by": self.produced_by,
                            "proposal_id": self.proposal_id,
                        }
                        for e in entries
                    ],
                )
                await session.commit()
        except Exception as exc:
            raise OutsideWritesUnrecorded(
                f"outside-write ledger unreachable: {len(entries)} write(s) by "
                f"{self.produced_by} under {root} are NOT recorded (ADR-169 D5): "
                f"{', '.join(e.path for e in entries)} -- {exc}"
            ) from exc
        del self.entries[: len(entries)]
        logger.info(
            "outside-write ledger: %d write(s) by %s under %s recorded",
            len(entries),
            self.produced_by,
            root,
        )
