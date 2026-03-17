# src/will/orchestration/phase_registry.py

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Protocol

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from shared.context import CoreContext
    from shared.models.workflow_models import PhaseResult
    from will.orchestration.workflow_orchestrator import WorkflowContext

logger = getLogger(__name__)


# ID: 286b11b7-caf7-4a0d-ad68-3672c988689d
class Phase(Protocol):
    # ID: 47fb1183-b447-4137-ac9a-7d5c37bab012
    async def execute(self, context: WorkflowContext) -> PhaseResult: ...


# ID: 32e40da7-32f5-4911-a5e9-aa30cb5a05b4
class PhaseRegistry:
    """
    Constitutional phase registry.

    Discovers phases from the constitutional repository.
    Loads only those phases that currently declare an executable implementation.
    """

    def __init__(self, core_context: CoreContext, path_resolver: PathResolver):
        self.context = core_context
        self._paths = path_resolver  # kept for constructor compatibility
        self._intent_repo = get_intent_repository()
        self._phases: dict[str, Phase] = {}
        self._phase_definitions: dict[str, dict] = {}

        self._load_phases()

    def _load_phases(self) -> None:
        discovered = 0
        loaded = 0
        skipped = 0

        for phase_id in self._intent_repo.list_phases():
            phase_def = self._intent_repo.load_phase(phase_id)

            phase_type = phase_def["phase_type"]
            self._phase_definitions[phase_type] = phase_def
            discovered += 1

            impl_path = phase_def.get("implementation")
            if not impl_path:
                skipped += 1
                logger.warning(
                    "Skipping constitutional phase '%s': no implementation declared yet",
                    phase_type,
                )
                continue

            module_path, class_name = impl_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            phase_class = getattr(module, class_name)

            self._phases[phase_type] = phase_class(self.context)
            loaded += 1

            logger.debug("Loaded phase: %s -> %s", phase_type, impl_path)

        logger.info(
            "PhaseRegistry initialized: discovered=%d loaded=%d skipped=%d",
            discovered,
            loaded,
            skipped,
        )

    # ID: 542111f2-a0fa-450e-91f8-47b8878e9907
    def get(self, phase_name: str) -> Phase:
        return self._phases[phase_name]

    # ID: d7276913-4bb9-42c2-af14-26245926ba4d
    def list_available(self) -> list[str]:
        return list(self._phases.keys())

    # ID: 6aeb89fb-c926-4e36-b7e7-81185a3f5695
    def get_definition(self, phase_name: str) -> dict:
        return self._phase_definitions[phase_name]
