# src/shared/infrastructure/context/service.py

"""
ContextService - main orchestrator for ContextPacket lifecycle.

Pipeline:
    ContextBuildRequest
        -> ContextBuilder
        -> ContextValidator
        -> ContextRedactor
        -> ContextSerializer

This service does not preserve legacy task_spec or query payload compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger

from .builder import ContextBuilder
from .cache import ContextCache
from .database import ContextDatabase
from .models import ContextBuildRequest, ContextPacket
from .providers.ast import ASTProvider
from .providers.db import DBProvider
from .providers.vectors import VectorProvider
from .redactor import ContextRedactor
from .serializers import ContextSerializer
from .validator import ContextValidator


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

logger = getLogger(__name__)


# ID: abac420e-2c78-4e00-bdae-56ce751388d7
class ContextService:
    """
    Main service for ContextPacket lifecycle management.
    """

    def __init__(
        self,
        qdrant_client: Any | None = None,
        cognitive_service: Any | None = None,
        config: dict[str, Any] | None = None,
        project_root: str = ".",
        session_factory: Any | None = None,
        workspace: LimbWorkspace | None = None,
    ) -> None:
        self.config = config or {}
        self.project_root = Path(project_root)
        self._session_factory = session_factory
        self.workspace = workspace

        self._qdrant_client = qdrant_client
        self._cognitive_service = cognitive_service

        self.validator = ContextValidator()
        self.redactor = ContextRedactor()
        self.cache = ContextCache(self.config.get("cache_dir", "work/context_cache"))
        self.database = ContextDatabase()
        self.ast_provider = ASTProvider(project_root)

        if self.workspace:
            logger.info("ContextService initialized in SHADOW mode")

    async def _ensure_brain_services(self) -> None:
        """
        Resolve vector/cognitive services JIT if missing at bootstrap.
        """
        if self._cognitive_service is None or self._qdrant_client is None:
            from body.services.service_registry import service_registry

            if self._cognitive_service is None:
                self._cognitive_service = await service_registry.get_cognitive_service()

            if self._qdrant_client is None:
                self._qdrant_client = await service_registry.get_qdrant_service()

    def _build_context_builder(self) -> ContextBuilder:
        db_provider = DBProvider(session_factory=self._session_factory)
        vector_provider = VectorProvider(self._qdrant_client, self._cognitive_service)

        return ContextBuilder(
            db_provider=db_provider,
            vector_provider=vector_provider,
            ast_provider=self.ast_provider,
            config=self.config,
            workspace=self.workspace,
        )

    # ID: b2fddb8f-af40-41d9-a45d-9af40ca1dc10
    async def build(
        self,
        request: ContextBuildRequest,
        use_cache: bool = True,
    ) -> ContextPacket:
        """
        Canonical entry point for context packet assembly.
        """
        await self._ensure_brain_services()

        effective_use_cache = use_cache if self.workspace is None else False
        cache_key = self._compute_request_cache_key(request)

        if effective_use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                return self._payload_to_packet(cached, request)

        builder = self._build_context_builder()
        packet = await builder.build(request)

        validation_result = self.validator.validate(packet)
        if not validation_result.ok:
            logger.error("Context packet rejected: %s", validation_result.errors)
            raise ValueError(f"Context validation failed: {validation_result.errors}")

        redacted_packet = self.redactor.redact(validation_result.validated_data)
        redacted_packet.setdefault("provenance", {})
        redacted_packet["provenance"]["packet_hash"] = (
            ContextSerializer.compute_packet_hash(redacted_packet)
        )

        if effective_use_cache:
            self.cache.set(cache_key, redacted_packet)

        return self._payload_to_packet(redacted_packet, request)

    # ID: 4f9a1c3e-7b82-4d56-a8e1-2c0f5e9d3a71
    async def build_for_task(
        self,
        task_spec: dict[str, Any],
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        Bridge: task_spec dict -> ContextBuildRequest -> ContextPacket -> legacy dict.

        Callers (code_generator, test_gen, conversational_agent) pass a task_spec
        dict and expect a plain dict back with a "context" key containing evidence
        items.  This method converts the dict to a typed ContextBuildRequest, calls
        the canonical build() pipeline, then re-shapes the ContextPacket back into
        the dict format those callers consume.

        task_spec shape (authoritative):
            {
                "task_id":       str,           # used as goal fallback
                "task_type":     str,           # maps to PhaseType
                "target_file":   str,           # primary target file
                "target_symbol": str,           # primary target symbol
                "summary":       str,           # becomes goal (preferred)
                "scope": {
                    "include":         list[str],   # additional target files
                    "traversal_depth": int,         # advisory, builder decides
                },
                "constraints": {
                    "max_tokens": int,              # advisory, builder decides
                    "max_items":  int,              # advisory, builder decides
                },
            }

        Returns a dict compatible with all existing callers:
            {
                "context":    list[dict],   # evidence items from ContextPacket
                "provenance": dict,
                "header":     dict,
            }
        """
        _PHASE_BY_TASK_TYPE: dict[str, str] = {
            "code_generation": "execution",
            "code_modification": "execution",
            "test_generation": "audit",
            "test.generate": "audit",
            "conversational": "runtime",
        }

        task_type = task_spec.get("task_type", "code_generation")
        target_file = task_spec.get("target_file", "")
        target_symbol = task_spec.get("target_symbol", "")
        # Prefer summary; fall back to task_id, then task_type
        goal = task_spec.get("summary") or task_spec.get("task_id") or task_type
        scope_include: list[str] = task_spec.get("scope", {}).get("include", [])
        phase = _PHASE_BY_TASK_TYPE.get(task_type, "execution")

        # Merge target_file with scope.include; deduplicate, preserve order, drop empties
        raw_files = ([target_file] if target_file else []) + list(scope_include)
        target_files = list(dict.fromkeys(f for f in raw_files if f))

        request = ContextBuildRequest(
            goal=goal,
            trigger="agent",  # type: ignore[arg-type]
            phase=phase,  # type: ignore[arg-type]
            target_files=target_files,
            target_symbols=[target_symbol] if target_symbol else [],
            include_constitution=True,
            include_policy=True,
            include_symbols=True,
            include_vectors=True,
            include_runtime=True,
        )

        packet = await self.build(request, use_cache=use_cache)

        # Re-shape ContextPacket -> legacy dict consumed by callers.
        # Callers index on "context"; ContextPacket stores evidence under .evidence.
        # The builder produces a list; the dataclass annotation says dict — guard both.
        evidence = packet.evidence
        if isinstance(evidence, dict):
            evidence = list(evidence.values()) if evidence else []

        context_count = len(evidence) if isinstance(evidence, list) else 0
        logger.info("Found %d context items for task_type=%s", context_count, task_type)

        return {
            "context": evidence,
            "provenance": packet.provenance,
            "header": packet.header,
        }

    def _compute_request_cache_key(self, request: ContextBuildRequest) -> str:
        payload = {
            "goal": request.goal,
            "trigger": request.trigger,
            "phase": request.phase,
            "workflow_id": request.workflow_id,
            "stage_id": request.stage_id,
            "target_files": list(request.target_files),
            "target_symbols": list(request.target_symbols),
            "target_paths": list(request.target_paths),
            "include_constitution": request.include_constitution,
            "include_policy": request.include_policy,
            "include_symbols": request.include_symbols,
            "include_vectors": request.include_vectors,
            "include_runtime": request.include_runtime,
        }
        return ContextSerializer.compute_cache_key(payload)

    def _payload_to_packet(
        self,
        payload: dict[str, Any],
        request: ContextBuildRequest,
    ) -> ContextPacket:
        return ContextPacket(
            request=request,
            header=payload.get("header", {}),
            layer_constraints=payload.get("layer_constraints", {}),
            constitution=payload.get("constitution", {}),
            policy=payload.get("policy", {}),
            constraints=payload.get("constraints", {}),
            evidence=payload.get("evidence", {}),
            runtime=payload.get("runtime", {}),
            provenance=payload.get("provenance", {}),
        )
