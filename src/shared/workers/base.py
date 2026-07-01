# src/shared/workers/base.py
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

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.logger import getLogger
from shared.workers.blackboard_publisher import BlackboardPublisher
from shared.workers.declaration_validator import validate_worker_declaration


logger = getLogger(__name__)


# ID: 5bd51595-1946-496c-9fc6-00c1a96acbc3
class WorkerConfigurationError(RuntimeError):
    """Raised when a Worker cannot load or validate its .intent/ declaration."""


# ID: 3f3d8cae-10d2-4ed7-bb70-d9d19fe70882
class WorkerRegistrationError(RuntimeError):
    """Raised when a Worker fails to register in worker_registry."""


# ID: e3ec800b-3683-48fd-b33c-181b140ee735
class WorkerSilenceError(RuntimeError):
    """Raised when a Worker's run() completes without posting any blackboard entry.

    Constitutional obligation: every Worker cycle MUST produce at least one
    blackboard entry via post_finding(), post_report(), or post_heartbeat().
    Silence (no entry) is a constitutional violation — the blackboard is the
    sole evidence of a Worker's work.
    """


@dataclass(frozen=True)
# ID: 6e048274-0303-4354-9018-07a12b57d9ec
class WorkerDeclaration:
    """Parsed `.intent/workers/*.yaml` declaration.

    Existence in `.intent/workers/` is the sole source of a worker's
    constitutional standing (per `.intent/META/worker.schema.json`).
    This dataclass governs the runtime shape that
    IntentRepository.load_worker() returns and that Worker.__init__
    stores as self._declaration. Nested object fields are kept as dicts
    rather than further nested dataclasses — the YAML→dict parse path is
    a single hop, and META/worker.schema.json already enforces the YAML
    side. Authority: ADR-056 Wave 1.
    """

    kind: str
    metadata: dict[str, Any]
    identity: dict[str, Any]
    mandate: dict[str, Any]
    implementation: dict[str, Any]
    config: dict[str, Any] | None = None


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

    def __init__(
        self, *, declaration_name: str = "", repo_root: Path | None = None
    ) -> None:
        # Instance-level override takes precedence over class attribute.
        # Allows one class to back multiple .intent/workers/ declarations.
        if declaration_name:
            self.declaration_name = declaration_name

        if not self.declaration_name:
            raise WorkerConfigurationError(
                f"{self.__class__.__name__} must set declaration_name — "
                "either as a class attribute or via the declaration_name constructor kwarg."
            )

        # Explicit repo_root bypasses the CWD-dependent global IntentRepository
        # singleton in _load_declaration. The daemon passes BootstrapRegistry.get_repo_path()
        # so container and test contexts with a non-CWD repo path resolve correctly.
        self._repo_root: Path | None = repo_root
        self._declaration = self._load_declaration()
        self._worker_uuid = uuid.UUID(self._declaration["identity"]["uuid"])
        self._worker_name = self._declaration["metadata"]["title"]
        self._worker_class = self._declaration["identity"]["class"]
        self._phase = self._declaration["mandate"]["phase"]
        self._approval_required = self._declaration["mandate"].get(
            "approval_required", True
        )

        self._blackboard = BlackboardPublisher(
            worker_uuid=self._worker_uuid,
            worker_name=self._worker_name,
            phase=self._phase,
            declaration=self._declaration,
        )
        self._cycle_post_count: int = 0

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
        """Register and run. Entry point for the scheduler.

        ADR-069 D8: the finally block releases any blackboard entries this
        worker still holds in status='claimed' at exit time — covering
        graceful shutdown (asyncio.CancelledError from systemctl stop),
        uncaught Exception, and the success path (idempotent: the WHERE
        clause filters entries already in a terminal status).

        ADR-104 D8 (the lease): a concurrent renewal task refreshes this
        worker's worker_registry.last_heartbeat for as long as run()
        executes. Heartbeats are otherwise posted only at run-start, so a
        claim-holder whose single run() exceeds the ADR-041 alive-threshold
        would fall out of the alive-set while still working and have its live
        claims reaped by the orphaned-claim sweep (ADR-104 D1). The lease
        keeps "stale heartbeat" honestly meaning "gone." This realizes the
        ADR-069 D2/D6 lease forecast for the ungraceful-exit recovery path.
        Claim-holders run via this start() path; self-scheduling workers
        (run_loop) re-heartbeat each short cycle and are out of scope.
        """
        await self._register()
        lease_task = asyncio.create_task(self._renew_lease_until_cancelled())
        try:
            self._cycle_post_count = 0
            await self.run()
            if self._cycle_post_count == 0:
                raise WorkerSilenceError(
                    f"Worker {self._worker_name!r} completed run() without posting "
                    "any blackboard entry — silence is a constitutional violation. "
                    "Call at least one of: post_finding(), post_report(), post_heartbeat()."
                )
        except Exception as e:
            await self._blackboard._post_entry(
                entry_type="report",
                subject="worker.error",
                payload={"error": str(e), "worker": self._worker_name},
                status="abandoned",
            )
            logger.error("Worker %s failed: %s", self._worker_name, e, exc_info=True)
            raise
        finally:
            lease_task.cancel()
            try:
                await lease_task
            except asyncio.CancelledError:
                pass
            except Exception as lease_err:
                logger.error(
                    "Worker %s lease task errored at shutdown: %s",
                    self._worker_name,
                    lease_err,
                    exc_info=True,
                )
            try:
                await self._release_held_claims()
            except Exception as release_err:
                # Never let release failures suppress the original exit
                # (CancelledError or the re-raised worker exception).
                logger.error(
                    "Worker %s failed to release held claims at shutdown: %s",
                    self._worker_name,
                    release_err,
                    exc_info=True,
                )

    async def _renew_lease_until_cancelled(self) -> None:
        """ADR-104 D8 — the liveness lease renewal loop.

        While run() executes, refresh worker_registry.last_heartbeat on a
        cadence shorter than the ADR-041 alive-threshold so the orphaned-claim
        reaper (ADR-104 D1) never mistakes a long-running claim-holder for
        dead. Registry-only touch — no blackboard heartbeat row per interval,
        just the timestamp the reaper reads. Cancelled by start()'s finally
        block when run() completes/fails/is cancelled. A renewal failure is
        logged and the loop continues; it must never crash the worker.
        """
        from shared.infrastructure.intent.operational_config import (
            load_operational_config,
        )

        interval = load_operational_config().health.worker_lease_renew_interval_sec
        while True:
            await asyncio.sleep(interval)
            try:
                await self._renew_registry_heartbeat()
            except Exception as exc:
                logger.warning(
                    "Worker %s lease renewal failed (will retry next interval): %s",
                    self._worker_name,
                    exc,
                )

    async def _renew_registry_heartbeat(self) -> None:
        """Refresh this worker's worker_registry.last_heartbeat (ADR-104 D8).

        Distinct from post_heartbeat(): updates only the registry liveness
        timestamp the reaper reads, not a blackboard heartbeat row — the lease
        proves liveness without emitting a per-interval heartbeat finding.
        """
        from sqlalchemy import text

        async with get_session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        update core.worker_registry
                           set last_heartbeat = now()
                         where worker_uuid = :worker_uuid
                        """
                    ),
                    {"worker_uuid": self._worker_uuid},
                )

    async def _release_held_claims(self) -> int:
        """Release any blackboard entries this worker still holds at exit.

        Single-statement UPDATE filtered by claimed_by + status='claimed' —
        idempotent across retries and across the three exit paths
        (success, exception, cancellation). Returns the count of rows
        actually released so callers (today: start()'s finally block) can
        log the shutdown effect.

        Constitutional position: the Worker base class is the right home
        for this — graceful pre-release is a property of the lifecycle
        contract, not a property of the blackboard service surface.
        """
        from sqlalchemy import text

        async with get_session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        update core.blackboard_entries
                           set status = 'open',
                               claimed_by = null,
                               updated_at = now()
                         where claimed_by = :worker_uuid
                           and status = 'claimed'
                        """
                    ),
                    {"worker_uuid": self._worker_uuid},
                )
                released = result.rowcount

        if released:
            logger.info(
                "Worker %s released %d held claim(s) at shutdown (ADR-069 D8)",
                self._worker_name,
                released,
            )
        return released

    # -------------------------------------------------------------------------
    # Blackboard API — subclasses use these to fulfill history obligation
    # Implemented by BlackboardPublisher; Worker thin-wraps for subclass
    # compatibility.  Inject a fake publisher in tests to avoid DB.
    # -------------------------------------------------------------------------

    # ID: e9594dc5-0100-49c1-9000-135b2613f7c0
    async def post_finding(
        self,
        subject: str,
        payload: dict[str, Any],
        *,
        resolution_mechanism: str,
    ) -> uuid.UUID:
        """Post a new finding to the blackboard. Returns the entry ID.

        See BlackboardPublisher.post_finding for the full contract.
        """
        self._cycle_post_count += 1
        return await self._blackboard.post_finding(
            subject, payload, resolution_mechanism=resolution_mechanism
        )

    # ID: 7f9d2a1c-3b8e-4d05-9c6f-1e8a7b4c2d50
    async def post_artifact_finding(
        self,
        artifact_type: str,
        sub_namespace: str,
        identity_key_value: str,
        payload: dict[str, Any],
    ) -> uuid.UUID:
        """Post a finding under the ADR-091 D2 canonical subject format.

        See BlackboardPublisher.post_artifact_finding for the full contract.
        """
        self._cycle_post_count += 1
        return await self._blackboard.post_artifact_finding(
            artifact_type, sub_namespace, identity_key_value, payload
        )

    # ID: 1b5d39a0-8d4c-475c-bcf5-5d50af2c6c2e
    async def post_report(self, subject: str, payload: dict[str, Any]) -> uuid.UUID:
        """Post a completion report to the blackboard."""
        self._cycle_post_count += 1
        return await self._blackboard.post_report(subject, payload)

    # ID: fdb25fd6-e20f-4e6c-b7bf-a39b2c60cc4e
    async def post_heartbeat(self) -> uuid.UUID:
        """Post a heartbeat — proves worker is alive and constitutionally compliant."""
        self._cycle_post_count += 1
        return await self._blackboard.post_heartbeat()

    # ID: 90d3435b-06b4-407e-8aee-7380942946c9
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> uuid.UUID:
        """Post an observability finding that is terminal at creation.

        See BlackboardPublisher.post_observation for the full contract.
        """
        self._cycle_post_count += 1
        return await self._blackboard.post_observation(subject, payload, status=status)

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

        Routes through IntentRepository (the canonical .intent/ gateway) per
        architecture.intent.no_legacy_root_assumptions and
        architecture.namespace.no_direct_protected_access.
        """
        from shared.infrastructure.intent.errors import GovernanceError

        worker_id = f"workers/{self.declaration_name}"

        # When an explicit repo_root is provided (e.g. injected by the daemon via
        # BootstrapRegistry.get_repo_path()), construct a dedicated IntentRepository
        # so the load is not sensitive to CWD or the global singleton's initialization
        # time. Callers that do not provide repo_root (tests, bare instantiation) fall
        # back to the global singleton, which uses settings.MIND / resolve_default_repo_path.
        repo_root = getattr(self, "_repo_root", None)
        if repo_root is not None:
            _repo = IntentRepository(root=repo_root / ".intent", strict=True)
        else:
            _repo = get_intent_repository()

        try:
            data = _repo.load_worker(worker_id)
        except GovernanceError as e:
            raise WorkerConfigurationError(
                f"Worker declaration not found: {worker_id}. "
                "A worker without a .intent/workers/ declaration has no constitutional standing."
            ) from e
        except Exception as e:
            raise WorkerConfigurationError(
                f"Failed to load worker declaration {worker_id}: {e}"
            ) from e

        # Schema validation (issue #460): the declaration must satisfy
        # .intent/META/worker.schema.json, including the canonical
        # worker_phase subset declared in .intent/META/enums.json.
        # Fails closed on missing/empty worker_phase, unresolved $ref,
        # or any structural violation.
        try:
            validate_worker_declaration(data, source=worker_id)
        except GovernanceError as e:
            raise WorkerConfigurationError(str(e)) from e

        try:
            uuid.UUID(data["identity"]["uuid"])
        except (KeyError, ValueError) as e:
            raise WorkerConfigurationError(
                f"Worker declaration {worker_id} has invalid or missing identity.uuid: {e}"
            ) from e

        if not data.get("mandate", {}).get("responsibility"):
            raise WorkerConfigurationError(
                f"Worker declaration {worker_id} is missing mandate.responsibility."
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
                            (worker_uuid, worker_name, worker_class, phase,
                             declaration_name, last_heartbeat)
                        values
                            (:worker_uuid, :worker_name, :worker_class, :phase,
                             :declaration_name, now())
                        on conflict (worker_uuid) do update set
                            worker_name = excluded.worker_name,
                            worker_class = excluded.worker_class,
                            phase = excluded.phase,
                            declaration_name = excluded.declaration_name,
                            last_heartbeat = now()
"""
                    ),
                    {
                        "worker_uuid": self._worker_uuid,
                        "worker_name": self._worker_name,
                        "worker_class": self._worker_class,
                        "phase": self._phase,
                        "declaration_name": self.declaration_name,
                    },
                )

        logger.info(
            "Worker registered: %s (uuid=%s)", self._worker_name, self._worker_uuid
        )
