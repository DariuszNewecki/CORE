# src/shared/workers/base.py
# ID: will.workers.base
"""
Worker Base Class - Constitutional Autonomous Entity.

A Worker is a constitutional officer with a single declared responsibility.
It is not an AI agent. Its authority comes from its .intent/workers/ declaration,
not from its capability or intelligence.

Constitutional obligations enforced here:
- Identity: UUID carried from .intent/workers/ declaration
- Registration: declared to worker_registry on startup
- History: every action written to blackboard — silence is a violation
- Scope: subclasses declare what they may touch
- Thoroughness over throughput: no speed pressure, correct output mandatory

LAYER: shared/workers — infrastructure shared by Will (sensing) and Body (acting).
DB access is legitimate here: blackboard IS the infrastructure.
"""

from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)

# PostgreSQL DB is SQL_ASCII encoded — non-ASCII characters cause
# UntranslatableCharacterError on insert. Sanitize all payload strings.
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")


# ID: 5bd51595-1946-496c-9fc6-00c1a96acbc3
class WorkerConfigurationError(RuntimeError):
    """Raised when a Worker cannot load or validate its .intent/ declaration."""


# ID: 3f3d8cae-10d2-4ed7-bb70-d9d19fe70882
class WorkerRegistrationError(RuntimeError):
    """Raised when a Worker fails to register in worker_registry."""


def _sanitize_str(value: str) -> str:
    """Replace non-ASCII characters with '?' for SQL_ASCII DB safety."""
    return _NON_ASCII_RE.sub("?", value)


def _sanitize_payload(obj: Any) -> Any:
    """Recursively sanitize all strings in a payload to printable ASCII."""
    if isinstance(obj, str):
        return _sanitize_str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(i) for i in obj]
    return obj


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f90
class Worker(ABC):
    """
    Constitutional base class for all autonomous Workers.

    Subclasses must:
    - Declare their mandate in .intent/workers/<n>.yaml
    - Implement run() — the single unit of constitutional work
    - Never communicate directly with other Workers (blackboard only)
    - Never execute proposals without approval if approval_required is True

    The declaration_name class attribute identifies which .intent/workers/ YAML
    this worker loads. Subclasses set it as a class attribute. The daemon may
    override it per-instance by passing declaration_name as a constructor kwarg —
    this enables one worker class to serve multiple namespace declarations.
    """

    # Subclasses set this to the filename stem in .intent/workers/
    # e.g. "doc_worker" → loads .intent/workers/doc_worker.yaml
    declaration_name: str = ""

    def __init__(self, *, declaration_name: str = "") -> None:
        # Instance-level override takes precedence over class attribute.
        # Allows one class to back multiple .intent/workers/ declarations.
        if declaration_name:
            self.declaration_name = declaration_name

        if not self.declaration_name:
            raise WorkerConfigurationError(
                f"{self.__class__.__name__} must set declaration_name — "
                "either as a class attribute or via the declaration_name constructor kwarg."
            )

        self._declaration = self._load_declaration()
        self._worker_uuid = uuid.UUID(self._declaration["identity"]["uuid"])
        self._worker_name = self._declaration["metadata"]["title"]
        self._worker_class = self._declaration["identity"]["class"]
        self._phase = self._declaration["mandate"]["phase"]
        self._approval_required = self._declaration["mandate"].get(
            "approval_required", True
        )

        logger.info(
            "Worker initialized: %s (uuid=%s, phase=%s)",
            self._worker_name,
            self._worker_uuid,
            self._phase,
        )

    # -------------------------------------------------------------------------
    # Abstract interface — subclasses implement this
    # -------------------------------------------------------------------------

    @abstractmethod
    # ID: 11fa4148-529e-46ca-be50-c2f0c9c5bf7e
    async def run(self) -> None:
        """
        Execute the worker's single declared responsibility.

        Constitutional contract:
        - Must write at least one blackboard entry (finding, report, or heartbeat)
        - Must not act outside declared scope
        - Must not communicate directly with other workers
        - Silence (no blackboard entry) is a constitutional violation
        """

    # -------------------------------------------------------------------------
    # Lifecycle — called by the scheduler / ShopManager
    # -------------------------------------------------------------------------

    # ID: 5a443e92-5798-4571-a3b0-63762bde2154
    async def start(self) -> None:
        """Register and run. Entry point for the scheduler."""
        await self._register()
        try:
            await self.run()
        except Exception as e:
            await self._post_entry(
                entry_type="report",
                subject="worker.error",
                payload={"error": str(e), "worker": self._worker_name},
                status="abandoned",
            )
            logger.error("Worker %s failed: %s", self._worker_name, e, exc_info=True)
            raise

    # -------------------------------------------------------------------------
    # Blackboard API — subclasses use these to fulfill history obligation
    # -------------------------------------------------------------------------

    # ID: e9594dc5-0100-49c1-9000-135b2613f7c0
    async def post_finding(self, subject: str, payload: dict[str, Any]) -> uuid.UUID:
        """Post a new finding to the blackboard. Returns the entry ID."""
        return await self._post_entry(
            entry_type="finding",
            subject=subject,
            payload=payload,
            status="open",
        )

    # ID: 1b5d39a0-8d4c-475c-bcf5-5d50af2c6c2e
    async def post_report(self, subject: str, payload: dict[str, Any]) -> uuid.UUID:
        """Post a completion report to the blackboard."""
        return await self._post_entry(
            entry_type="report",
            subject=subject,
            payload=payload,
            status="resolved",
        )

    # ID: fdb25fd6-e20f-4e6c-b7bf-a39b2c60cc4e
    async def post_heartbeat(self) -> uuid.UUID:
        """Post a heartbeat — proves worker is alive and constitutionally compliant."""
        return await self._post_entry(
            entry_type="heartbeat",
            subject="worker.heartbeat",
            payload={"worker": self._worker_name, "ts": datetime.now(UTC).isoformat()},
            status="resolved",
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    # ID: 3d1e1a06-082d-409a-a841-371630dbe282
    def worker_uuid(self) -> uuid.UUID:
        return self._worker_uuid

    @property
    # ID: 872ec2e4-196e-405a-91e2-74a03437dcbe
    def worker_name(self) -> str:
        return self._worker_name

    @property
    # ID: 304ce819-0fcd-413d-a21b-cc04a5220285
    def phase(self) -> str:
        return self._phase

    @property
    # ID: 183205fe-8afc-4f35-9fef-754707efd7fd
    def approval_required(self) -> bool:
        return self._approval_required

    @property
    # ID: 69c9d675-cb32-47a8-895a-38f4a41deb0e
    def declaration(self) -> dict[str, Any]:
        return self._declaration

    # -------------------------------------------------------------------------
    # Internal — constitutional machinery
    # -------------------------------------------------------------------------

    def _load_declaration(self) -> dict[str, Any]:
        """
        Load and validate this worker's .intent/workers/ declaration.

        The declaration is the constitutional source of truth for:
        - worker UUID (permanent identity)
        - mandate (responsibility, phase, scope, tools)
        - approval requirements
        """
        intent_root = Path(".intent").resolve()
        declaration_path = intent_root / "workers" / f"{self.declaration_name}.yaml"

        if not declaration_path.exists():
            raise WorkerConfigurationError(
                f"Worker declaration not found: {declaration_path}. "
                f"A worker without a .intent/workers/ declaration has no constitutional standing."
            )

        try:
            data = strict_yaml_processor.load_strict(declaration_path)
        except Exception as e:
            raise WorkerConfigurationError(
                f"Failed to load worker declaration {declaration_path}: {e}"
            ) from e

        try:
            uuid.UUID(data["identity"]["uuid"])
        except (KeyError, ValueError) as e:
            raise WorkerConfigurationError(
                f"Worker declaration {declaration_path} has invalid or missing identity.uuid: {e}"
            ) from e

        if not data.get("mandate", {}).get("responsibility"):
            raise WorkerConfigurationError(
                f"Worker declaration {declaration_path} is missing mandate.responsibility."
            )

        return data

    async def _register(self) -> None:
        """
        Declare this worker's identity in worker_registry.

        Called on startup. ShopManagers validate registration against
        .intent/workers/ declarations. Unregistered workers cannot post
        to the blackboard with constitutional authority.
        """
        from sqlalchemy import text

        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        insert into core.worker_registry
                            (worker_uuid, worker_name, worker_class, phase, status, last_heartbeat)
                        values
                            (:worker_uuid, :worker_name, :worker_class, :phase, 'active', now())
                        on conflict (worker_uuid) do update set
                            status = 'active',
                            last_heartbeat = now()
                    """
                    ),
                    {
                        "worker_uuid": self._worker_uuid,
                        "worker_name": self._worker_name,
                        "worker_class": self._worker_class,
                        "phase": self._phase,
                    },
                )

        logger.info(
            "Worker registered: %s (uuid=%s)", self._worker_name, self._worker_uuid
        )

    async def _post_entry(
        self,
        *,
        entry_type: str,
        subject: str,
        payload: dict[str, Any],
        status: str,
    ) -> uuid.UUID:
        """
        Write a constitutional record to the blackboard.

        Every decision, finding, and report must be recorded here.
        This is the enforcement point for the history obligation.

        Payload is sanitized to ASCII before insert — the DB is SQL_ASCII
        encoded and will reject non-ASCII characters with UntranslatableCharacterError.
        """
        import json

        from sqlalchemy import text

        entry_id = uuid.uuid4()

        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        insert into core.blackboard_entries
                            (id, worker_uuid, entry_type, phase, status, subject, payload, resolved_at)
                        values
                            (:id, :worker_uuid, :entry_type, :phase, :status, :subject, cast(:payload as jsonb),
                             case when :status in ('resolved', 'abandoned', 'indeterminate') then now() else null end)
                    """
                    ),
                    {
                        "id": entry_id,
                        "worker_uuid": self._worker_uuid,
                        "entry_type": entry_type,
                        "phase": self._phase,
                        "status": status,
                        "subject": subject,
                        "payload": json.dumps(_sanitize_payload(payload)),
                    },
                )

                if entry_type == "heartbeat":
                    await session.execute(
                        text(
                            """
                            update core.worker_registry
                            set last_heartbeat = now(), status = 'active'
                            where worker_uuid = :worker_uuid
                        """
                        ),
                        {"worker_uuid": self._worker_uuid},
                    )

        logger.debug(
            "Blackboard entry posted: type=%s subject=%s id=%s",
            entry_type,
            subject,
            entry_id,
        )
        return entry_id
