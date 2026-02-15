# src/will/orchestration/phase_registry.py
# ID: 72fdbdd6-5697-4a26-8bc7-d946388b2ee7

"""
Phase Registry - Dynamically discovers and maps phase types to implementations

Constitutional Design:
- Phases are discovered from .intent/phases/*.yaml (single source of truth)
- Implementation classes register themselves via PHASE_IMPLEMENTATIONS
- Registry validates that constitutional phases have implementations
- Clear separation between definition (Constitution) and implementation (Code)
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Protocol

import yaml

from shared.logger import getLogger
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from shared.context import CoreContext
    from shared.models.workflow_models import PhaseResult
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: d33552dd-a098-4cbc-a901-35b5f3f1ea49
class Phase(Protocol):
    """Protocol for phase implementations"""

    # ID: 7d581046-ae42-498e-baea-8184cfc16436
    async def execute(self, context: WorkflowContext) -> PhaseResult:
        """Execute this phase with given context"""
        ...


# Phase implementation registration
# Maps phase_type → fully qualified class path
# ID: 8132f134-4092-4a87-b9b5-73534025c0f9
PHASE_IMPLEMENTATIONS = {
    "interpret": "will.phases.interpret_phase.InterpretPhase",
    "planning": "will.phases.planning_phase.PlanningPhase",
    "code_generation": "will.phases.code_generation_phase.CodeGenerationPhase",
    "test_generation": "will.phases.test_generation_phase.TestGenerationPhase",
    "canary_validation": "will.phases.canary_validation_phase.CanaryValidationPhase",
    "sandbox_validation": "will.phases.sandbox_validation_phase.SandboxValidationPhase",
    "style_check": "will.phases.style_check_phase.StyleCheckPhase",
    "execution": "will.phases.execution_phase.ExecutionPhase",
}


# ID: a2e84b0e-f502-4823-9f35-c549ac77e315
# ID: ad3208cb-4266-4153-a07c-1a566faae733
class PhaseRegistry:
    """
    Registry of available phase implementations.

    Discovers phases from .intent/phases/*.yaml and dynamically
    loads corresponding implementations.
    """

    def __init__(self, core_context: CoreContext, path_resolver: PathResolver):
        self.context = core_context
        self._paths = path_resolver
        self._phases: dict[str, Phase] = {}
        self._phase_definitions: dict[str, dict] = {}
        self._initialize_phases()

    def _initialize_phases(self):
        """
        Discover phases from .intent/phases/ and instantiate implementations.

        Process:
        1. Scan .intent/phases/*.yaml for phase definitions
        2. Load each phase definition
        3. Look up implementation class from PHASE_IMPLEMENTATIONS
        4. Dynamically import and instantiate
        5. Warn if phase defined but not implemented
        """
        phase_dir = self._paths.intent_root / "phases"

        if not phase_dir.exists():
            logger.warning("⚠️  Phase directory not found: %s", phase_dir)
            return

        discovered_phases = []
        implemented_phases = []
        missing_implementations = []

        for yaml_file in sorted(phase_dir.glob("*.yaml")):
            try:
                phase_def = yaml.safe_load(yaml_file.read_text())
                phase_type = phase_def["phase_type"]

                discovered_phases.append(phase_type)
                self._phase_definitions[phase_type] = phase_def

                # Look up implementation
                if phase_type in PHASE_IMPLEMENTATIONS:
                    impl_path = PHASE_IMPLEMENTATIONS[phase_type]
                    phase_class = self._import_class(impl_path)
                    self._phases[phase_type] = phase_class(self.context)
                    implemented_phases.append(phase_type)
                    logger.debug("✅ Loaded phase: %s → %s", phase_type, impl_path)
                else:
                    missing_implementations.append(phase_type)
                    logger.warning(
                        "⚠️  Phase '%s' defined in .intent but no implementation registered",
                        phase_type,
                    )

            except Exception as e:
                logger.error(
                    "❌ Failed to load phase from %s: %s",
                    yaml_file.name,
                    e,
                    exc_info=True,
                )

        logger.info(
            "📋 PhaseRegistry initialized: %d discovered, %d implemented, %d missing",
            len(discovered_phases),
            len(implemented_phases),
            len(missing_implementations),
        )

        if missing_implementations:
            logger.warning(
                "⚠️  Missing implementations: %s", ", ".join(missing_implementations)
            )

    def _import_class(self, class_path: str):
        """
        Dynamically import a class from a fully qualified path.

        Args:
            class_path: e.g. "will.phases.planning_phase.PlanningPhase"

        Returns:
            The class object
        """
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    # ID: 6f1c4099-f4d5-401a-b74f-21f7ae6e3006
    def get(self, phase_name: str) -> Phase:
        """Get phase implementation by name"""
        if phase_name not in self._phases:
            available = list(self._phases.keys())
            raise KeyError(f"Unknown phase: {phase_name}. " f"Available: {available}")
        return self._phases[phase_name]

    # ID: e87034ff-10b3-4a75-ad8d-c51884b96ac4
    def list_available(self) -> list[str]:
        """List all registered phase types"""
        return list(self._phases.keys())

    # ID: d181996f-c5a5-49a2-8303-fe0f048d12a1
    # ID: e57374f5-4cac-4bb0-abb2-4c5b41736973
    def get_definition(self, phase_name: str) -> dict:
        """
        Get the constitutional definition for a phase.

        Returns the parsed YAML from .intent/phases/{phase_name}.yaml
        """
        if phase_name not in self._phase_definitions:
            raise KeyError(f"No definition found for phase: {phase_name}")
        return self._phase_definitions[phase_name]
