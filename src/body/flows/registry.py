# src/body/flows/registry.py
"""
Flow Registry — loads constitutional Flow declarations from .intent/flows/.

Flows are declared in .intent/flows/*.yaml — the same pattern as Workers
in .intent/workers/*.yaml. Existence in .intent/flows/ is constitutional
standing. A Flow not declared there cannot be referenced in a Proposal
or invoked via FlowExecutor.

Constitutional alignment: CORE-Flow.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 25e5756f-76ef-4c18-be17-5a98814d8e32
class StepKind(str, Enum):
    """Whether a step references an AtomicAction, another Flow, or a cognitive operation."""

    ACTION = "action"
    FLOW = "flow"
    COGNITIVE = "cognitive"
    """
    Will-tier generation step. Body dispatches to an injected CognitiveFlowDelegate;
    it never executes cognition itself. ADR-140 D2.
    """


@dataclass(frozen=True)
# ID: 502f3080-f3e3-4b2c-909f-a1b25e9465b8
class FlowStep:
    """
    A single step in a Flow's declared sequence.

    Each step references either an action_id (AtomicAction), a flow_id (nested
    Flow), or a cognitive operation identifier (Will-tier delegate). Steps are
    executed in declaration order.
    """

    ref_id: str
    """action_id, flow_id, or cognitive operation identifier this step resolves to."""

    kind: StepKind
    """Whether ref_id is an action, a flow, or a cognitive step."""

    required: bool = True
    """
    If True, failure halts the Flow and returns ok=False.
    If False, failure is recorded but execution continues.
    """

    params: dict = field(default_factory=dict)
    """
    Static parameters passed to this step at execution time.
    Merged with any runtime params supplied by the caller.
    Caller params take precedence over static params.
    """

    consumes: tuple[str, ...] | None = None
    """
    Allowlist of caller-param keys this step is allowed to receive.

    None (or absent) = all caller params are forwarded to this step.
    This is the safe default — silent swallow is a worse failure mode
    than an unexpected-kwarg TypeError in a governed system (see #445).
    A tuple of key names = only those keys are forwarded from the
    caller; everything else is dropped. An empty tuple drops everything
    explicitly. Static ``params`` always pass through regardless of
    this field.
    """

    produces: tuple[str, ...] | None = None
    """
    Output keys this step places into accumulated params for downstream steps.

    Only meaningful for COGNITIVE steps — Body write steps consume, not produce.
    None = no output threading (backward-compatible default for ACTION/FLOW steps).
    FlowExecutor validates that all declared keys are present in the step's output
    and fails loudly if any are missing (ADR-140 D4).
    """


@dataclass
# ID: 61668ef8-6327-45e6-9789-f1c738d2d410
class FlowDefinition:
    """
    Constitutional declaration of a Flow, loaded from .intent/flows/*.yaml.

    Existence in the FlowRegistry means the declaration was found in
    .intent/flows/, parsed, and validated. A Flow not in the registry
    has no constitutional standing.
    """

    flow_id: str
    """Unique dot-notation identifier. e.g. flow.fix_code"""

    description: str
    """One sentence describing what this Flow does."""

    steps: list[FlowStep]
    """Ordered sequence of steps. Executed top to bottom."""

    policies: list[str]
    """Policy IDs governing this Flow."""

    generation_mode: str = "single_shot"
    """
    Generation strategy declared for this flow (ADR-135 D5).
    'single_shot' (default) or 'iterative'. Read by the CognitiveFlowDelegate
    to select strategy; does NOT govern which delegate is constructed.
    """

    cognitive_capability: str | None = None
    """
    Capability identifier for CognitiveFlowDelegate selection (ADR-140 D9).
    ProposalExecutor maps this to a concrete delegate class.
    None = no cognitive steps in this flow.
    """

    source_path: Path | None = None
    """The .intent/flows/*.yaml file this definition was loaded from."""


# ID: a7feea5d-3278-4808-8655-3c72940e1eea
class FlowRegistry:
    """
    Global registry of all constitutional Flows in CORE.

    Loaded from .intent/flows/*.yaml at first access. Mirrors the
    worker registry loading pattern. FlowExecutor resolves
    flow_id -> FlowDefinition via this registry.
    """

    def __init__(self) -> None:
        self._flows: dict[str, FlowDefinition] = {}
        self._loaded: bool = False

    # ID: b09a007b-1a44-426f-a028-fcb2d524a0c0
    def load(self) -> None:
        """
        Load all Flow declarations from .intent/flows/ via IntentRepository.

        Called once at startup. Subsequent calls are no-ops.
        Skips files with status != 'active'. Logs warnings for
        malformed declarations without halting.
        """
        if self._loaded:
            return

        for yaml_path, data in get_intent_repository().iter_flow_documents():
            self._load_entry(yaml_path, data)

        self._loaded = True
        logger.info("FlowRegistry: loaded %d flow(s)", len(self._flows))

    # ID: a5974a87-eb95-4bef-bab1-e516b2b8faf5
    def _load_entry(self, yaml_path: Path, data: dict) -> None:
        """Register a single flow declaration from a pre-parsed dict."""

        status = data.get("metadata", {}).get("status", "active")
        if status != "active":
            logger.info(
                "FlowRegistry: skipping %s (status=%s)",
                yaml_path.name,
                status,
            )
            return

        flow_block = data.get("flow", {})
        flow_id = flow_block.get("flow_id")
        description = flow_block.get("description", "").strip()
        policies = flow_block.get("policies", [])
        generation_mode = str(data.get("generation_mode", "single_shot"))
        cognitive_capability = data.get("cognitive_capability") or None
        raw_steps = flow_block.get("steps", [])

        if not flow_id:
            logger.warning(
                "FlowRegistry: %s missing flow.flow_id — skipped",
                yaml_path.name,
            )
            return

        steps: list[FlowStep] = []
        for raw in raw_steps:
            ref_id = raw.get("ref_id")
            kind_str = raw.get("kind", "action")
            required = raw.get("required", True)
            params = raw.get("params", {}) or {}
            raw_consumes = raw.get("consumes")
            consumes = tuple(raw_consumes) if raw_consumes is not None else None
            raw_produces = raw.get("produces")
            produces = tuple(raw_produces) if raw_produces is not None else None

            if not ref_id:
                logger.warning(
                    "FlowRegistry: step in %s missing ref_id — step skipped",
                    yaml_path.name,
                )
                continue

            try:
                kind = StepKind(kind_str)
            except ValueError:
                logger.warning(
                    "FlowRegistry: unknown step kind '%s' in %s — step skipped",
                    kind_str,
                    yaml_path.name,
                )
                continue

            steps.append(
                FlowStep(
                    ref_id=ref_id,
                    kind=kind,
                    required=required,
                    params=params,
                    consumes=consumes,
                    produces=produces,
                )
            )

        if not steps:
            logger.warning(
                "FlowRegistry: %s has no valid steps — skipped",
                yaml_path.name,
            )
            return

        if flow_id in self._flows:
            logger.warning(
                "FlowRegistry: duplicate flow_id '%s' in %s — skipped",
                flow_id,
                yaml_path.name,
            )
            return

        definition = FlowDefinition(
            flow_id=flow_id,
            description=description,
            steps=steps,
            policies=policies,
            generation_mode=generation_mode,
            cognitive_capability=cognitive_capability,
            source_path=yaml_path,
        )
        self._flows[flow_id] = definition
        logger.debug(
            "FlowRegistry: registered '%s' (%d steps) from %s",
            flow_id,
            len(steps),
            yaml_path.name,
        )

    # ID: 4e4b68bd-978f-45f7-8b2e-62de5d97b1dc
    def get(self, flow_id: str) -> FlowDefinition | None:
        """Resolve a flow_id to its FlowDefinition. Returns None if not found."""
        self._ensure_loaded()
        return self._flows.get(flow_id)

    # ID: 6815a5ef-14d3-44cb-a555-657020b2398b
    def list_all(self) -> list[FlowDefinition]:
        """List all registered Flows."""
        self._ensure_loaded()
        return list(self._flows.values())

    # ID: 2d422ecb-e161-4250-b2a3-5b09959d0f7a
    def _ensure_loaded(self) -> None:
        """Lazy-load from .intent/flows/ via IntentRepository if not yet loaded."""
        if not self._loaded:
            self.load()


# Global singleton — mirrors action_registry pattern
flow_registry = FlowRegistry()
