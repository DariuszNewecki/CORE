# src/shared/infrastructure/intent/task_type_phases.py
# ID: shared.infrastructure.intent.task_type_phases
"""
Task-type to governance-phase mapping helper.

Single source of truth for the ExecutionTask.task_type vocabulary and
its mapping to the governance PhaseType. Both the mapping and the
closed vocabulary are owned by
.intent/enforcement/config/task_type_phases.yaml.

Authority: policy. The governing document is
.intent/enforcement/config/task_type_phases.yaml, accessed exclusively
via IntentRepository. No other module may hardcode the task_type ->
phase mapping — all call sites route through this helper. See ADR-004.

The _FALLBACK_* constants below are last-resort graceful degradation
for the narrow case where the policy document cannot be loaded (e.g.
bootstrap races, corrupt YAML). They MUST NOT be treated as
defaults-in-logic — when the policy loads successfully, it always wins.

LAYER: shared/infrastructure/intent — pure helper. No imports from
will/, body/, or cli/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.context.models import PhaseType


logger = getLogger(__name__)


_VALID_PHASES: frozenset[str] = frozenset(
    {"parse", "load", "audit", "runtime", "execution"}
)

_FALLBACK_DEFAULT_PHASE = "execution"
_FALLBACK_MAPPING: dict[str, str] = {
    "code_generation": "execution",
    "code_modification": "execution",
    "test_generation": "audit",
    "test.generate": "audit",
    "conversational": "runtime",
}


def _validate_config(config: dict[str, Any]) -> None:
    """
    Validate at load time that every phase value in the config is a
    member of the PhaseType Literal set. Raises ValueError with a
    clear message on the first offending key/value encountered.
    """
    default_phase = config.get("default_phase")
    if default_phase is None or default_phase not in _VALID_PHASES:
        raise ValueError(
            f"task_type_phases: default_phase {default_phase!r} is not a "
            f"valid PhaseType; allowed values are {sorted(_VALID_PHASES)}"
        )

    mapping = config.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError(
            "task_type_phases: 'mapping' must be a dict of task_type -> phase"
        )

    for task_type, phase in mapping.items():
        if phase not in _VALID_PHASES:
            raise ValueError(
                f"task_type_phases: mapping[{task_type!r}] = {phase!r} is not "
                f"a valid PhaseType; allowed values are {sorted(_VALID_PHASES)}"
            )


# ID: c1d2e3f4-a5b6-4708-9c1d-2e3f4a5b6c7d
def load_task_type_phases() -> dict[str, Any]:
    """
    Load .intent/enforcement/config/task_type_phases.yaml via IntentRepository.

    Returns the parsed policy dict on success. On any failure — missing
    file, parse error, unexpected top-level type — returns fallback
    defaults and logs a warning so callers degrade gracefully rather
    than halting.

    The loader validates every phase value against the PhaseType Literal
    set before returning. A YAML that maps a task_type to a phase
    outside {parse, load, audit, runtime, execution} raises ValueError
    at load time, not at the call site.
    """
    try:
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        repo = get_intent_repository()
        config_path = repo.resolve_rel("enforcement/config/task_type_phases.yaml")
        config = repo.load_document(config_path)
        if isinstance(config, dict):
            _validate_config(config)
            return config
        logger.warning(
            "task_type_phases: task_type_phases.yaml did not parse as a dict "
            "— using fallback defaults."
        )
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(
            "task_type_phases: could not load .intent/enforcement/config/"
            "task_type_phases.yaml (%s) — using fallback defaults.",
            exc,
        )
    return {
        "default_phase": _FALLBACK_DEFAULT_PHASE,
        "mapping": dict(_FALLBACK_MAPPING),
    }


# ID: d2e3f4a5-b6c7-4819-ad2e-3f4a5b6c7d8e
def resolve_phase(
    task_type: str,
    config: dict[str, Any] | None = None,
) -> PhaseType:
    """
    Return the governance phase for a task_type.

    Falls back to config['default_phase'] when task_type is not in the
    mapping. If config is None, load_task_type_phases() is called.

    The returned value is typed as PhaseType: the loader has already
    validated that every phase value is a member of the PhaseType
    Literal set, so callers may pass the result directly to
    ContextBuildRequest(phase=...) without a type: ignore.
    """
    if config is None:
        config = load_task_type_phases()

    mapping = config.get("mapping", {})
    default_phase: str = config.get("default_phase", _FALLBACK_DEFAULT_PHASE)
    phase: str = mapping.get(task_type, default_phase)
    return phase  # type: ignore[return-value]


# ID: e3f4a5b6-c7d8-491a-be3f-4a5b6c7d8e9f
def allowed_task_types(
    config: dict[str, Any] | None = None,
) -> frozenset[str]:
    """
    Return the closed vocabulary — the keys of config['mapping'].

    Used by shared.models.execution_models at import time to populate
    the ExecutionTask.task_type field_validator's allowed set. If
    config is None, load_task_type_phases() is called.
    """
    if config is None:
        config = load_task_type_phases()
    mapping = config.get("mapping", {})
    return frozenset(mapping.keys())
