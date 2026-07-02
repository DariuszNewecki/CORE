# src/mind/logic/engines/registry.py

"""
Dynamic Registry of Governance Engines.
Uses Introspection to discover and initialize engines at runtime.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any, ClassVar

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.llm.client import LLMClient
    from shared.path_resolver import PathResolver

logger = getLogger(__name__)

# Metadata-only engines defined in YAML that should be handled silently.
# Source of truth: .intent/taxonomies/substrate_enforcement.yaml (ADR-136 D1).
# This set is the cold-start fallback; EngineRegistry.initialize() replaces it
# with the taxonomy's entry keys once a path_resolver is available.
PASSIVE_ALIASES: set[str] = {
    "python_runtime",
    "type_system",
    "runtime_metric",
    "advisory",
    "runtime_check",
    "dataclass_validation",
}


# ID: f80b6018-9642-4f69-bfcb-d5ab35f7b1d1
class EngineRegistry:
    """
    Dynamic Registry for Governance Engines.
    Automatically discovers engines in the current package.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _engine_classes: ClassVar[dict[str, type]] = {}
    _path_resolver: ClassVar[PathResolver | None] = None
    _llm_client: ClassVar[LLMClient | None] = None
    _embedding_client: ClassVar[Any | None] = None
    _discovered: ClassVar[bool] = False

    @classmethod
    # ID: b0cfcefb-27db-4db3-b5e7-754e1d16c958
    def initialize(
        cls,
        path_resolver: PathResolver,
        llm_client: LLMClient | None = None,
        embedding_client: Any | None = None,
    ) -> None:
        """Reset registry state and re-run engine discovery.

        Clears both cached instances AND the discovered-engine-class map,
        then triggers a fresh discovery pass. Auditor re-init at the start
        of each audit run (auditor.py) relies on this to pick up engine
        files added since process start — without resetting ``_discovered``
        a new engine module is invisible until the process restarts.
        Caught by ADR-079 Slice B (taxonomy_gate) which shipped against a
        long-running core-api and went undiscovered until manual restart.
        """
        cls._path_resolver = path_resolver
        cls._llm_client = llm_client
        cls._embedding_client = embedding_client
        cls._instances.clear()
        cls._engine_classes.clear()
        cls._discovered = False
        cls._discover_engines()
        cls._load_passive_aliases_from_taxonomy()
        logger.debug("EngineRegistry primed with dynamic discovery.")

    @classmethod
    def _discover_engines(cls):
        """Scans the engines directory for BaseEngine implementations."""
        if cls._discovered:
            return

        import mind.logic.engines as engines_pkg

        from .base import BaseEngine

        for _, name, _ in pkgutil.iter_modules(engines_pkg.__path__):
            try:
                module = importlib.import_module(
                    f".{name}", package="mind.logic.engines"
                )
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseEngine) and obj is not BaseEngine:
                        eid = getattr(obj, "engine_id", name)
                        cls._engine_classes[eid] = obj
            except Exception as e:
                logger.warning("Failed to load engine module %s: %s", name, e)

        cls._discovered = True

    @classmethod
    def _load_passive_aliases_from_taxonomy(cls) -> None:
        """Reload PASSIVE_ALIASES from the substrate-enforcement taxonomy (ADR-136 D4).

        Replaces the module-level constant with the taxonomy's entry keys so the
        runtime registry and the governance file cannot silently diverge. Failures
        are non-fatal: the cold-start constant remains in effect.
        """
        if cls._path_resolver is None:
            return
        import yaml

        global PASSIVE_ALIASES
        taxonomy_path = (
            cls._path_resolver.repo_root
            / ".intent"
            / "taxonomies"
            / "substrate_enforcement.yaml"
        )
        try:
            data = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
            entries = data.get("entries", {})
            if isinstance(entries, dict) and entries:
                PASSIVE_ALIASES = set(entries.keys())
                logger.debug(
                    "EngineRegistry: loaded %d passive aliases from taxonomy.",
                    len(PASSIVE_ALIASES),
                )
        except Exception as exc:
            logger.warning(
                "EngineRegistry: could not load substrate_enforcement.yaml (%s); "
                "using cold-start PASSIVE_ALIASES fallback.",
                exc,
            )

    @classmethod
    # ID: 8ef22fc4-2090-41a6-b59c-f6167a0f832c
    def engine_source_files(cls) -> frozenset[str]:
        """Repo-relative POSIX source paths of every registered engine module.

        The canonical answer to "which source files ARE audit engines." Used by
        the assisted lane to detect a self-referential fix: a diff that patches
        an engine cannot be validated by the in-process auditor, because the
        worktree patch does not change the engine logic the validator runs
        (#661). Derived from the registered classes' modules, so it tracks the
        registry rather than a hardcoded engines-directory literal. Discovery is
        idempotent and needs no path_resolver (it only reads class modules).
        """
        cls._discover_engines()
        return frozenset(
            "src/" + klass.__module__.replace(".", "/") + ".py"
            for klass in cls._engine_classes.values()
        )

    @classmethod
    # ID: 69a7916b-b8f4-4509-bb2c-897eec528adf
    def get(cls, engine_id: str) -> Any:
        if cls._path_resolver is None:
            raise ValueError("EngineRegistry not initialized.")

        # HEAL: Resolve Passive Aliases to the passive_gate
        target_id = "passive_gate" if engine_id in PASSIVE_ALIASES else engine_id

        if target_id in cls._instances:
            return cls._instances[target_id]

        if target_id not in cls._engine_classes:
            # Re-run discovery just in case
            cls._discover_engines()
            if target_id not in cls._engine_classes:
                raise ValueError(f"Unsupported Governance Engine: {engine_id}")

        engine_cls = cls._engine_classes[target_id]

        # JIT Initialization with Smart Injection
        # We check the constructor to see what dependencies the engine actually wants.
        sig = inspect.signature(engine_cls.__init__)
        params = {}

        if "path_resolver" in sig.parameters:
            params["path_resolver"] = cls._path_resolver

        if "llm_client" in sig.parameters:
            # Provide stub if real client is missing
            if cls._llm_client:
                params["llm_client"] = cls._llm_client
            else:
                from .llm_gate_stub import LLMGateStubEngine

                logger.debug("Redirecting %s to Stub (No LLM Client)", target_id)
                return LLMGateStubEngine()

        if "embedding_client" in sig.parameters:
            params["embedding_client"] = cls._embedding_client

        cls._instances[target_id] = engine_cls(**params)
        return cls._instances[target_id]
