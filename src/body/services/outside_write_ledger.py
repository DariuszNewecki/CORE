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
    ...write dest...
    log.wrote(dest)          # sha256 of the bytes now on disk
    ...delete dest...
    log.deleted(dest)
    await log.flush()        # one INSERT batch into core.outside_writes

Each entry: target root, target-relative path, operation (write / delete),
sha256 of the written bytes, producer. No content and no secret material is
recorded — only the hash.

When the ledger cannot be reached (e.g. ``project new`` on a host without
CORE's database), the writes have already happened: ``flush`` logs an error
naming every unrecorded path and returns False. It never raises — the same
posture as the ADR-169 D1 boot observation (a ledger failure is visible, not
fatal).

Constitutional standing: body/services. Reads the files it hashes; writes
only to the database. No LLM calls.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from sqlalchemy import text

from shared.logger import getLogger
from shared.workers.blackboard_publisher import _sanitize_payload


logger = getLogger(__name__)

OutsideOperation = Literal["write", "delete"]


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

    # ID: 808d86b9-dbaa-4b2c-a57a-ed547e884e24
    async def flush(self) -> bool:
        """Append every collected entry to core.outside_writes and clear them.

        Returns True when recorded (or nothing to record), False when the
        ledger could not be reached — logged as an error naming the paths.
        """
        if not self.entries:
            return True
        entries, self.entries = self.entries, []
        root = Path(self.target_root).resolve().as_posix()
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
            logger.error(
                "outside-write ledger unreachable: %d write(s) by %s under %s are "
                "NOT recorded (ADR-169 D5): %s -- %s",
                len(entries),
                self.produced_by,
                root,
                ", ".join(e.path for e in entries),
                exc,
            )
            return False
        logger.info(
            "outside-write ledger: %d write(s) by %s under %s recorded",
            len(entries),
            self.produced_by,
            root,
        )
        return True
