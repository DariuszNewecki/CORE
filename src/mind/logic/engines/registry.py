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


# ID: 5e62aff7-edfd-4808-8833-9dd9ebc63757
class DuplicateEngineIdError(RuntimeError):
    """Two different engine classes declare the same engine_id (ADR-176 D5a).
    CORE refuses to start rather than let one replace the other silently."""


# ID: f80b6018-9642-4f69-bfcb-d5ab35f7b1d1
class EngineRegistry:
    """
    Dynamic Registry for Governance Engines.
    Automatically discovers engines in the current package.
    """

    _instances: ClassVar[dict[str, Any]] = {}
    _engine_classes: ClassVar[dict[str, type]] = {}
    # Where each registered class came from: "built-in" or "plug-in <name> <version>".
    _engine_sources: ClassVar[dict[str, str]] = {}
    # The plug-ins loaded by the last discovery (ADR-177).
    _plugins: ClassVar[list[Any]] = []
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
        cls._engine_sources.clear()
        cls._plugins = []
        cls._discovered = False
        # Aliases first: registration checks ids against them (ADR-176 D6).
        cls._load_passive_aliases_from_taxonomy()
        cls._discover_engines()
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
                found = [
                    obj
                    for _, obj in inspect.getmembers(module, inspect.isclass)
                    if issubclass(obj, BaseEngine) and obj is not BaseEngine
                ]
            except Exception as e:
                # ADR-176 D7: a module that fails to import stays a warning.
                logger.warning("Failed to load engine module %s: %s", name, e)
                continue
            # Outside the try: a refusal (ADR-176 D5a) is not an import failure.
            for obj in found:
                cls._register(obj, default_id=name)

        cls._discover_plugins()
        cls._discovered = True

    @classmethod
    def _discover_plugins(cls) -> None:
        """ADR-177 D2/D3: every installed plug-in, after the built-ins, its
        engines through the same registration point."""
        from shared.infrastructure.plugins import installed_plugins

        from .base import CORE_ENGINE_API

        cls._plugins = installed_plugins(CORE_ENGINE_API)
        for plugin in cls._plugins:
            for engine_cls in plugin.engines:
                cls._register(
                    engine_cls,
                    default_id=engine_cls.__module__.rsplit(".", 1)[-1],
                    source=f"plug-in {plugin.label}",
                )

    @classmethod
    def _register(
        cls, engine_cls: type, *, default_id: str, source: str = "built-in"
    ) -> None:
        """The one registration point (ADR-176 D4): every engine class enters
        the registry here, whatever source found it.

        D5(a): a different class with an id already held refuses the start
        and names both; the same class met twice (re-exported by another
        module) is not a duplicate.
        """
        from .base import CORE_ENGINE_API
        from .contract import api_version_problem, d6_problems, engine_id_of

        engine_id = engine_id_of(engine_cls, default_id)
        name = f"{engine_cls.__module__}.{engine_cls.__qualname__}"
        api_version = str(getattr(engine_cls, "api_version", "1"))
        if api_version_problem(engine_cls) is not None:
            logger.warning(
                "Engine %s (%s) declares api_version %r; this CORE supports "
                "%r. Not registered; its rules give the engine-missing "
                "finding (ADR-176 D5(b)).",
                engine_id,
                name,
                api_version,
                CORE_ENGINE_API,
            )
            return
        held = cls._engine_classes.get(engine_id)
        if held is not None and held is not engine_cls:
            held_source = cls._engine_sources.get(engine_id, "built-in")
            raise DuplicateEngineIdError(
                f"Two engines declare engine_id {engine_id!r}: "
                f"{held.__module__}.{held.__qualname__} ({held_source}) and "
                f"{engine_cls.__module__}.{engine_cls.__qualname__} ({source}) "
                "(ADR-176 D5(a), ADR-177 D5)"
            )
        for problem in d6_problems(engine_cls, engine_id, PASSIVE_ALIASES):
            logger.warning(
                "Engine %s (%s): %s. A warning in 3.x, a refusal in 4.0 (ADR-176 D6).",
                engine_id,
                name,
                problem,
            )
        cls._engine_classes[engine_id] = engine_cls
        cls._engine_sources[engine_id] = source

    @classmethod
    def _load_passive_aliases_from_taxonomy(cls) -> None:
        """Reload PASSIVE_ALIASES from the substrate-enforcement taxonomy (ADR-136 D4).

        Replaces the module-level constant with the taxonomy's entry keys so the
        runtime registry and the governance file cannot silently diverge. Failures
        are non-fatal: the cold-start constant remains in effect.
        """
        if cls._path_resolver is None:
            return
        from shared.infrastructure.intent.intent_repository import get_intent_repository

        global PASSIVE_ALIASES
        repo = get_intent_repository()
        if not repo.has_policy("taxonomies/substrate_enforcement"):
            # An adopter project need not declare the taxonomy; the built-in set
            # is the substrate default, not a degraded state (#957). A declared
            # but unreadable taxonomy still warns below.
            logger.debug(
                "EngineRegistry: no substrate_enforcement taxonomy declared; "
                "using the built-in PASSIVE_ALIASES."
            )
            return
        try:
            data = repo.load_policy("taxonomies/substrate_enforcement")
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
    # ID: 3d00f0ce-5b6f-428a-97d6-f4b3dc2e3a37
    def graph_dependent_engine_files(cls) -> frozenset[str]:
        """Repo-relative POSIX source paths of engines that require the knowledge graph.

        Graph-dependent engines (``requires_knowledge_graph = True``) cannot be
        subprocess-validated in the assisted lane: the DB knowledge graph is
        stale relative to a worktree patch. ADR-141 D2.

        The canonical answer to "which engine files must refuse the subprocess
        audit path." Derived from registered classes, not a hardcoded path list.
        """
        cls._discover_engines()
        return frozenset(
            "src/" + klass.__module__.replace(".", "/") + ".py"
            for klass in cls._engine_classes.values()
            if getattr(klass, "requires_knowledge_graph", False)
        )

    @classmethod
    # ID: ff3f2570-dd46-46c0-8bcc-f0252015d15a
    def engine_class(cls, engine_id: str) -> type | None:
        """The engine class for ``engine_id``, without building it, or None
        when the registry holds no such engine. A passive alias resolves to
        ``passive_gate``. Needs no initialization: discovery only imports
        engine modules."""
        cls._discover_engines()
        target_id = "passive_gate" if engine_id in PASSIVE_ALIASES else engine_id
        return cls._engine_classes.get(target_id)

    @classmethod
    # ID: 4b8e2f6a-9c1d-4e7b-a3f5-0d6c8b2e4a91
    def known_engine_ids(cls) -> frozenset[str]:
        """Every engine id a rule or catalog may name: discovered engines plus
        passive aliases, which ``get`` resolves to ``passive_gate``.

        Read by the catalog contract (ADR-174 D8) to flag an unknown id at
        load instead of at evaluation. Needs no initialization: discovery only
        imports engine modules.
        """
        cls._discover_engines()
        return frozenset(cls._engine_classes) | frozenset(PASSIVE_ALIASES)

    @classmethod
    # ID: 4508f4fb-3139-417d-8a2a-e68e72d57c89
    def record_catalogs(cls) -> dict[str, Any]:
        """Every record catalog a discovered engine ships, by catalog id
        (ADR-173 D15). Read from the engine classes, so CORE names no engine
        module to find them. Needs no initialization."""
        cls._discover_engines()
        catalogs: dict[str, Any] = {}
        for klass in cls._engine_classes.values():
            hook = getattr(klass, "record_catalogs", None)
            if callable(hook):
                catalogs.update(hook())
        return catalogs

    @classmethod
    # ID: d9971ee2-20ff-42c0-ba89-1d923150490d
    def record_engine(cls, engine_id: str) -> Any:
        """An instance of a record-capable engine (ADR-173 D1). Record
        engines are pure and take no injected services, so this needs no
        initialization. Raises ValueError for an unknown engine or one that
        does not judge records; the evaluator turns that into the
        engine-missing finding."""
        cls._discover_engines()
        klass = cls._engine_classes.get(engine_id)
        if klass is None:
            raise ValueError(f"Unsupported Governance Engine: {engine_id}")
        if not getattr(klass, "supports_records", False):
            raise ValueError(f"Engine {engine_id} does not judge records")
        # ADR-176 D3: built at most once per registry initialization, like get().
        if engine_id not in cls._instances:
            cls._instances[engine_id] = klass()
        return cls._instances[engine_id]

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
        sig = inspect.signature(engine_cls.__init__)  # type: ignore[misc]
        params: dict[str, Any] = {}

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
