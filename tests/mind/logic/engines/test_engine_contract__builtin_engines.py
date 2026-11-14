"""ADR-176 baseline (#1339 PR B): the built-in engines as they are on main.

Pins what ADR-176 D2 says an engine declares, measured on the 18 engines
CORE ships today, before any src/ change of #1339:

- the registry holds exactly these 18 ids, each mapped to this class;
- each class sets ``engine_id`` on itself (not inherited, not derived from
  the module name);
- no engine id equals a passive alias;
- each constructor requires only ``path_resolver``, ``llm_client`` or
  ``embedding_client``.

Later #1339 PRs must keep these tests green without editing them.
"""

from __future__ import annotations

import inspect

import pytest

import mind.logic.engines.registry as registry_module
from mind.logic.engines.registry import EngineRegistry


# engine_id -> "module.ClassName", as on main e3fce34e / ae831345.
_BUILTIN_ENGINES: dict[str, str] = {
    "artifact_gate": "mind.logic.engines.artifact_gate.ArtifactGateEngine",
    "ast_gate": "mind.logic.engines.ast_gate.engine.ASTGateEngine",
    "attestation_gate": "mind.logic.engines.attestation_gate.AttestationGateEngine",
    "cli_gate": "mind.logic.engines.cli_gate.engine.CliGateEngine",
    "contracts_gate": "mind.logic.engines.contracts_gate.ContractsGateEngine",
    "exclusion_gate": "mind.logic.engines.exclusion_gate.ExclusionGateEngine",
    "glob_gate": "mind.logic.engines.glob_gate.GlobGateEngine",
    "grc_judge": "mind.logic.engines.grc_judge.GRCJudgeEngine",
    "knowledge_gate": "mind.logic.engines.knowledge_gate.KnowledgeGateEngine",
    "llm_gate": "mind.logic.engines.llm_gate.LLMGateEngine",
    "llm_gate_stub": "mind.logic.engines.llm_gate_stub.LLMGateStubEngine",
    "passive_gate": "mind.logic.engines.passive_gate.PassiveGateEngine",
    "publication_gate": "mind.logic.engines.publication_gate.PublicationGateEngine",
    "reference_gate": "mind.logic.engines.reference_gate.ReferenceGateEngine",
    "regex_gate": "mind.logic.engines.regex_gate.RegexGateEngine",
    "schema_gate": "mind.logic.engines.schema_gate.SchemaGateEngine",
    "taxonomy_gate": "mind.logic.engines.taxonomy_gate.TaxonomyGateEngine",
    "workflow_gate": "mind.logic.engines.workflow_gate.engine.WorkflowGateEngine",
}

# ADR-176 D2: the only services CORE injects.
_INJECTED = frozenset({"path_resolver", "llm_client", "embedding_client"})

# engine_id -> constructor parameters without a default, as on main.
_REQUIRED_CONSTRUCTOR_PARAMS: dict[str, frozenset[str]] = {
    "ast_gate": frozenset({"path_resolver"}),
    "cli_gate": frozenset({"path_resolver"}),
    "grc_judge": frozenset({"path_resolver", "llm_client"}),
    "llm_gate": frozenset({"path_resolver", "llm_client"}),
    "reference_gate": frozenset({"path_resolver"}),
    "taxonomy_gate": frozenset({"path_resolver"}),
    "workflow_gate": frozenset({"path_resolver"}),
}


def _required_params(cls: type) -> frozenset[str]:
    sig = inspect.signature(cls.__init__)  # type: ignore[misc]
    return frozenset(
        name
        for name, param in sig.parameters.items()
        if name != "self"
        and param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        and param.default is inspect.Parameter.empty
    )


def test_registry_holds_exactly_the_18_builtin_engines(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    found = {
        engine_id: f"{cls.__module__}.{cls.__qualname__}"
        for engine_id, cls in fresh_engine_registry._engine_classes.items()
    }
    assert found == _BUILTIN_ENGINES
    assert len(found) == 18


@pytest.mark.parametrize("engine_id", sorted(_BUILTIN_ENGINES))
def test_engine_declares_its_engine_id_on_its_own_class(
    fresh_engine_registry: type[EngineRegistry], engine_id: str
) -> None:
    cls = fresh_engine_registry._engine_classes[engine_id]
    assert "engine_id" in vars(cls), f"{cls.__qualname__} inherits engine_id"
    assert vars(cls)["engine_id"] == engine_id


def test_no_engine_id_equals_a_passive_alias(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    # After initialize the aliases come from the taxonomy (ADR-136 D4).
    aliases = set(registry_module.PASSIVE_ALIASES)
    assert aliases, "no passive aliases loaded"
    assert set(fresh_engine_registry._engine_classes).isdisjoint(aliases)


@pytest.mark.parametrize("engine_id", sorted(_BUILTIN_ENGINES))
def test_constructor_requires_only_injected_services(
    fresh_engine_registry: type[EngineRegistry], engine_id: str
) -> None:
    required = _required_params(fresh_engine_registry._engine_classes[engine_id])
    assert required <= _INJECTED, f"{engine_id} requires {sorted(required - _INJECTED)}"
    assert required == _REQUIRED_CONSTRUCTOR_PARAMS.get(engine_id, frozenset())
