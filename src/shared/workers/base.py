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

import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.processors.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)

CORE_ROLE = "facade"  # ADR-095 D3

# PostgreSQL DB is SQL_ASCII encoded — non-ASCII characters cause
# UntranslatableCharacterError on insert. Sanitize all payload strings.
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")

# Terminal statuses per .intent/META/enums.json (blackboard_entry_status).
# A row in any of these states cannot be claimed or transitioned by a
# worker without explicit revival. post_observation() enforces that its
# `status` argument is in this set so observability findings are
# constitutionally terminal at creation — no SLA accumulation, no
# stale-alert spam from BlackboardShopManager.
_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        "resolved",
        "abandoned",
        "suppressed",
        "dry_run_complete",
        "indeterminate",
        "deferred_to_proposal",
    }
)


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
    """Recursively sanitize all strings in a payload to printable ASCII.

    Dict keys are sanitized in addition to values — JSONB write paths
    under SQL_ASCII reject non-ASCII in keys just as they do in values,
    and the prior key-pass-through gap (closed by #348) made the
    promise in the previous docstring untrue.
    """
    if isinstance(obj, str):
        return _sanitize_str(obj)
    if isinstance(obj, dict):
        return {_sanitize_payload(k): _sanitize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_payload(i) for i in obj]
    return obj


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
        """Register and run. Entry point for the scheduler.

        ADR-069 D8: the finally block releases any blackboard entries this
        worker still holds in status='claimed' at exit time — covering
        graceful shutdown (asyncio.CancelledError from systemctl stop),
        uncaught Exception, and the success path (idempotent: the WHERE
        clause filters entries already in a terminal status). The lease
        mechanism (ADR-069 D2/D6, future work) remains the recovery path
        for ungraceful exits where the finally block cannot run.
        """
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
        finally:
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

        The single, canonical finding-posting API under ADR-091 D2
        Revision B. ``resolution_mechanism`` declares which authority class
        may close this finding and gates ADR-045 awaiting_reaudit
        eligibility — the invariant is:

            A finding may be transitioned to awaiting_reaudit if and only
            if its resolution_mechanism = 'reaudit'.

        Permitted values (closed set per
        ``.intent/META/enums.json`` ``finding_resolution_mechanism``):

        - ``reaudit`` — the owning audit/sensor worker re-evaluates the
          subject's truth claim against a re-readable artifact; eligible
          for ADR-045's parked-revival queue. Artifact findings posted
          via :meth:`post_artifact_finding` carry this automatically.
        - ``self_resolve`` — the posting supervisor worker (or a service
          it explicitly delegates to) owns the open → resolved transition
          on a later cycle when live state recovers. Not eligible for
          awaiting_reaudit. The emitting worker's module docstring MUST
          name the resolver path per Revision B (d)'s resolver-ownership
          invariant.
        - ``human`` — closing authority is a human operator only, via
          ``core-admin blackboard resolve``. Not eligible for
          awaiting_reaudit; conservative default for findings with no
          automated closer.

        ``resolution_mechanism`` is keyword-only with no default so every
        caller classifies at the call site (same write-boundary discipline
        ADR-011 imposes on attribution). The DB-side CHECK enforces the
        closed set; no raw-SQL bypass exists.

        For artifact findings (re-readable subjects with a typed
        ``artifact_type`` declaration) prefer :meth:`post_artifact_finding`
        — it constructs the canonical
        ``<artifact_type>::<sub_namespace>::<identity_key_value>`` subject
        and supplies ``resolution_mechanism="reaudit"`` for you.
        """
        return await self._post_entry(
            entry_type="finding",
            subject=subject,
            payload=payload,
            status="open",
            resolution_mechanism=resolution_mechanism,
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

        The framework constructs the subject string from typed parameters:
        ``f"{artifact_type}::{sub_namespace}::{identity_key_value}"``.

        Validation (ADR-091 D2):
        - ``artifact_type`` must appear in this worker's declared
          ``mandate.scope.artifact_type`` array. When the list is absent or
          empty (Phase 1 transition allowance — sensor declarations not yet
          updated), validation no-ops with a debug log.
        - ``sub_namespace`` must equal this worker's declared
          ``mandate.scope.rule_namespace`` or extend it via dotted suffix
          (e.g. ``test.runner`` permits ``test.runner.missing``). Same
          transition allowance applies when ``rule_namespace`` is absent.

        Phase 1 of ADR-091 D5 introduced this API alongside
        ``post_finding(subject, payload)``. Sensors migrated to this method
        through Phases 3, 5, and 6. Under Revision B of the D2 amendment
        (accepted 2026-06-05) ``post_finding`` is the single canonical
        finding API and is retained — this method is its typed-parameter
        wrapper for artifact findings, supplying ``resolution_mechanism =
        "reaudit"`` automatically. The Phase 6 commit-2 "remove the legacy
        method" plan is superseded.
        """
        scope = self._declaration["mandate"].get("scope") or {}
        declared_types = scope.get("artifact_type") or []
        declared_namespace = scope.get("rule_namespace")

        if declared_types and artifact_type not in declared_types:
            raise ValueError(
                f"post_artifact_finding: artifact_type {artifact_type!r} not in "
                f"declared mandate.scope.artifact_type {declared_types!r}. "
                f"Per ADR-091 D2, sensors may only emit findings under "
                f"artifact types they have declared they observe."
            )
        if not declared_types:
            logger.debug(
                "post_artifact_finding called by %s with no declared "
                "artifact_type; ADR-091 Phase 1 transition allowance applies",
                self._worker_name,
            )

        if declared_namespace:
            if sub_namespace != declared_namespace and not sub_namespace.startswith(
                f"{declared_namespace}."
            ):
                raise ValueError(
                    f"post_artifact_finding: sub_namespace {sub_namespace!r} "
                    f"must equal declared rule_namespace {declared_namespace!r} "
                    f"or extend it via dotted suffix. Per ADR-091 D2 the "
                    f"sub-namespace must equal or extend the sensor's declared "
                    f"rule_namespace."
                )
        else:
            logger.debug(
                "post_artifact_finding called by %s with no declared "
                "rule_namespace; ADR-091 Phase 1 transition allowance applies",
                self._worker_name,
            )

        subject = f"{artifact_type}::{sub_namespace}::{identity_key_value}"
        return await self.post_finding(
            subject=subject,
            payload=payload,
            resolution_mechanism="reaudit",
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

    # ID: 90d3435b-06b4-407e-8aee-7380942946c9
    async def post_observation(
        self, subject: str, payload: dict[str, Any], *, status: str
    ) -> uuid.UUID:
        """Post an observability finding that is terminal at creation.

        Use this for records that have no remediation pathway — events the
        system observed but no worker will claim and resolve (yields,
        detection-only audits, infrastructure error records). The caller
        MUST specify which terminal status applies, since the semantic
        choice is meaningful per .intent/META/enums.json:

        - abandoned: "workers gave up but the underlying issue persists;
          sensor MAY re-emit on a fresh detection." Right for transient
          failures (sync.db.failed) and for per-event records where the
          same root condition recurs (yield receipts). worker.silent is
          NOT a canonical example here — under ADR-091 D2 Revision B it
          is a self_resolve open finding (post_finding with
          resolution_mechanism='self_resolve'), not a terminal-at-creation
          observation; the resolver is WorkerShopManager's in-Python
          resolve_entries pass when the worker resumes heartbeating.
        - indeterminate: "no worker may claim or transition without
          explicit revival." Right for detection-only audits that need
          governor review (orphan SHA detection).
        - dry_run_complete: dedicated terminal for dry-run records.
        - suppressed: governor signal that the subject must not be
          surfaced again.
        - resolved: completion records that look like findings rather
          than reports (rare; prefer post_report).
        - deferred_to_proposal: when the finding has been folded into a
          proposal whose lifecycle now owns the resolution.

        Posting with status='open' is forbidden here — that's what
        post_finding is for. Using post_finding for an observability
        subject causes BlackboardShopManager to accumulate stale-alerts
        forever (the alert sweep only resolves when target reaches
        terminal). ADR-069 / #observability-TTL recon, 2026-05-25.
        """
        if status not in _TERMINAL_STATUSES:
            raise ValueError(
                f"post_observation requires a terminal status (got '{status}'). "
                f"Permitted: {sorted(_TERMINAL_STATUSES)}. "
                f"Use post_finding for status='open' (actionable findings) "
                f"or post_report for status='resolved' completion records."
            )
        if status == "indeterminate":
            # Indeterminate is "permanent until explicit governor revival"
            # per this function's contract. Re-emission for the same subject
            # is categorically a contract violation, not a soft duplicate.
            # The caller-level dedup in CommitReachabilityAuditor was lost
            # in the post_finding -> post_observation migration (#450) and
            # silently accumulated 861 duplicate rows over 10 days. This
            # API-layer guard makes the contract enforceable regardless of
            # caller discipline.
            from sqlalchemy import text

            async with get_session() as session:
                result = await session.execute(
                    text(
                        """
                        SELECT 1 FROM core.blackboard_entries
                        WHERE subject = :subject
                          AND status = 'indeterminate'
                          AND entry_type = 'finding'
                        LIMIT 1
                        """
                    ),
                    {"subject": subject},
                )
                if result.first() is not None:
                    raise ValueError(
                        f"post_observation refuses duplicate indeterminate "
                        f"post for subject={subject!r}. Indeterminate "
                        f"findings are permanent until explicit governor "
                        f"revival; re-emission is a contract violation. "
                        f"Use BlackboardService."
                        f"fetch_active_finding_subjects_by_prefix to dedup "
                        f"before posting."
                    )
        return await self._post_entry(
            entry_type="finding",
            subject=subject,
            payload=payload,
            status=status,
            # ADR-091 D2 Revision B: observation findings are
            # terminal-at-creation records with no automated closer; they
            # match the constitutional definition of the `human` closing
            # authority ("no automated closer at all"). Classifying them
            # `human` also keeps them constitutionally barred from
            # awaiting_reaudit by the same predicate that guards
            # self_resolve findings, which is correct — observations have
            # no re-readable artifact for an audit sensor to re-evaluate.
            resolution_mechanism="human",
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

        # Schema validation (issue #460): the declaration must satisfy
        # .intent/META/worker.schema.json, including the canonical
        # worker_phase subset declared in .intent/META/enums.json.
        # Fails closed on missing/empty worker_phase, unresolved $ref,
        # or any structural violation.
        from shared.infrastructure.intent.errors import GovernanceError
        from shared.workers.declaration_validator import validate_worker_declaration

        try:
            validate_worker_declaration(data, source=declaration_path)
        except GovernanceError as e:
            raise WorkerConfigurationError(str(e)) from e

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

    async def _post_entry(
        self,
        *,
        entry_type: str,
        subject: str,
        payload: dict[str, Any],
        status: str,
        resolution_mechanism: str | None = None,
    ) -> uuid.UUID:
        """
        Write a constitutional record to the blackboard.

        Every decision, finding, and report must be recorded here.
        This is the enforcement point for the history obligation.

        Payload is sanitized to ASCII before insert — the DB is SQL_ASCII
        encoded and will reject non-ASCII characters with UntranslatableCharacterError.

        resolution_mechanism is non-omittable for entry_type='finding' (the
        callers post_finding / post_artifact_finding enforce that at their
        signatures) and forbidden for every other entry_type. The DB-side
        CHECK blackboard_entry_resolution_mechanism_closed_set enforces both
        halves; see ADR-091 D2 Revision B.
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
                            (id, worker_uuid, entry_type, phase, status, subject, payload, resolution_mechanism, resolved_at)
                        values
                            (:id, :worker_uuid, :entry_type, :phase, :status, :subject, cast(:payload as jsonb),
                             :resolution_mechanism,
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
                        "resolution_mechanism": resolution_mechanism,
                    },
                )

                if entry_type == "heartbeat":
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

        logger.debug(
            "Blackboard entry posted: type=%s subject=%s id=%s",
            entry_type,
            subject,
            entry_id,
        )
        return entry_id
