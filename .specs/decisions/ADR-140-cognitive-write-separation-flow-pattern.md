---
kind: adr
id: ADR-140
title: "ADR-140 — Cognitive-Write Separation: The Flow Cognitive Step Pattern"
status: accepted
---

<!-- path: .specs/decisions/ADR-140-cognitive-write-separation-flow-pattern.md -->

# ADR-140 — Cognitive-Write Separation: The Flow Cognitive Step Pattern

**Date:** 2026-07-05
**Status:** Accepted
**Authority:** Architectural
**Band:** B — Core Architecture
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-05)
**Grounding:** ADR-135 D1/D5 (dual-mode generation; FlowExecutor routing intent);
`architecture.boundary.llm_client_access` (blocking — Body MUST NOT make AI decisions);
`architecture.layers.no_body_to_will` (reporting — Body MUST NOT invoke Will)
**Closes:** ADR-135 D5 (FlowExecutor cognitive routing — never implemented)
**First consumer:** `flow.build_test_for_symbol` / `build.test_for_symbol` action

---

## Context

### The drift

`src/body/atomic/build_test_for_symbol_action.py` is a Body-layer atomic action that
contains three Will-tier responsibilities:

1. **Prompt loading** — `PromptModel.load("context_aware_test_gen")` at the Body layer (L178)
2. **Cognitive client acquisition** — `core_context.cognitive_service.aget_client_for_role()`
   at the Body layer (L182)
3. **Iterative repair loop** — ~180 lines (L214–391) of generate → IntentGuard → feed
   violations back → repeat, up to the governed cap from `generation_budget.yaml`

All three violate `architecture.boundary.llm_client_access`: "Only Will and autonomous
services MAY import LLM client infrastructure; Body MUST NOT make AI decisions."

This drift was acknowledged at ADR-135 D2 implementation time. `IterativeCoderAgent`'s
docstring carries an explicit architecture note: "build.test_for_symbol uses PromptModel
.invoke() directly rather than CoderAgent, so its iterative loop is implemented inside the
action (Body tier)." It was accepted as temporary debt, not a principled design.

### Why it persisted

ADR-135 D5 prescribed: "FlowExecutor reads `generation_mode` from the flow manifest and
routes the generation step accordingly." This was never implemented. At the time, `generation_mode`
was an *action parameter* — `generation_mode: str = GenerationMode.SINGLE_SHOT` (L124) —
not a flow-level field. `FlowExecutor` forwarded it as a step param; the action read it and
routed internally. The intended routing — FlowExecutor → Will-tier primitive — was blocked
by three constraints:

1. **`FlowExecutor` is Body.** It cannot import or invoke Will-tier agents directly
   (`architecture.layers.no_body_to_will`).
2. **No inter-step data threading.** `FlowExecutor` passes the same `caller_params` to
   every step. A generation step's output (`generated_code`) cannot reach the downstream
   write step.
3. **`IterativeCoderAgent` wraps `CoderAgent`.** `build.test_for_symbol` uses
   `PromptModel.invoke()` directly with specific context variables that do not fit
   `CoderAgent.generate_or_repair`'s `ExecutionTask`-based interface. Plugging it through
   `IterativeCoderAgent` without adapting `CoderAgent` was not possible.

ADR-135 D5's routing intent was architecturally correct; the mechanism it prescribed was
not reachable without the design additions this ADR provides.

### The general pattern this ADR solves

Any CORE flow that requires LLM generation faces the same structural problem: the action
that writes the generated artifact is the natural terminal step in a flow, but the
generation loop — with its prompts, repair cycles, and acceptance conditions — is Will-tier
orchestration that must not live inside a Body action. This is not unique to test generation.
Any future flow involving AI generation (code repair, documentation, schema inference) faces
the same challenge. This ADR establishes the reusable solution.

---

## The invariant

**Body atomic actions are terminal write operations. They receive pre-generated artifacts
as parameters. They MUST NOT load prompts, acquire cognitive clients, or run iterative
generation loops.**

The separation boundary is the `generated_artifact` parameter: Will-tier cognitive steps
produce it; Body write steps consume it. No Body action may cross that boundary.

---

## Decisions

### D1 — The Cognitive-Write Separation invariant is constitutional

Any Body atomic action whose purpose is to write a generated artifact MUST:
- Accept `generated_<artifact>` (e.g. `generated_code`) as a required parameter
- Perform at most one validation pass on the received artifact
- Write the artifact via `FileHandler`
- NEVER load a `PromptModel`, acquire a cognitive client, or run a generation loop

Any flow that requires LLM generation MUST declare the generation step as
`kind: cognitive` (D2) and the write step as `kind: action`.

This invariant is verifiable by static import analysis. Regression tests for Body write
actions MUST assert that the action module does not import prompt loading or cognitive
client infrastructure (D10).

### D2 — `StepKind.COGNITIVE` — new flow step kind

`src/body/flows/registry.py` gains a new `StepKind` value:

```python
class StepKind(str, Enum):
    ACTION    = "action"
    FLOW      = "flow"
    COGNITIVE = "cognitive"   # Will-tier generation step; Body dispatches, never executes
```

The name `COGNITIVE` is drawn from CORE's existing vocabulary (`CognitiveProtocol`,
`cognitive_service`, `CognitiveEmbedderAdapter`). It signals *what* is being delegated.
Body does not execute cognition; it dispatches to an injected `CognitiveFlowDelegate`
protocol (D3). The step kind name and execution site are deliberately distinct.

`FlowStep` gains a new optional field:

```python
@dataclass(frozen=True)
class FlowStep:
    ...
    produces: tuple[str, ...] | None = None
    """
    Output keys this step places into accumulated params for downstream steps.
    Only meaningful for COGNITIVE steps. None = no output threading (default).
    """
```

`FlowRegistry._load_entry` must also parse `produces` from each step's YAML block and pass
it into the `FlowStep(...)` constructor — omitting this makes the threading mechanism
silently inert (`step.produces` stays `None` for every step, so D4's guard never fires and
`generated_code` never reaches the write step):

```python
# In the per-step parsing loop inside _load_entry:
raw_produces = raw.get("produces")
produces = tuple(raw_produces) if raw_produces is not None else None

# In the FlowStep(...) construction:
steps.append(
    FlowStep(
        ref_id=ref_id,
        kind=kind,
        required=required,
        params=params,
        consumes=consumes,
        produces=produces,   # new
    )
)
```

Flow YAML declares cognitive steps as:

```yaml
steps:
  - ref_id: generate.test_snippet      # identifies the cognitive operation
    kind: cognitive
    required: true
    consumes: [source_file, symbol_name, symbol_kind, signature]
    produces: [generated_code]

  - ref_id: build.test_for_symbol
    kind: action
    required: true
    consumes: [source_file, symbol_name, symbol_kind, generated_code, write]
```

The `ref_id` of a cognitive step is a stable identifier for the cognitive operation, not
a registered action_id. The `CognitiveFlowDelegate` (D3) resolves it.

### D3 — `CognitiveFlowDelegate` protocol in `shared/protocols/`

A new protocol in `src/shared/protocols/cognitive_flow_delegate.py` defines the
Body/Will boundary contract:

```python
class CognitiveFlowDelegate(Protocol):
    async def execute_cognitive_step(
        self,
        step_ref: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a cognitive step identified by step_ref.

        Returns a dict of output keys that will be threaded into downstream
        steps as params (per the step's produces declaration).

        Raises CognitiveStepError if step_ref is unknown or generation fails.
        """
        ...
```

`FlowExecutor` (Body) depends on this protocol from `shared`. It never imports Will
implementations directly. This is the same DI pattern established by `ActionExecutorProtocol`
(`shared/protocols/executor.py`) for Will → Body mutations.

**The invariant this creates:** Body executes cognitive steps only when a Will-tier delegate
is injected. Without injection, encountering a cognitive step is an explicit error (D4).

### D4 — FlowExecutor: cognitive routing and inter-step threading

`FlowExecutor.__init__` gains an optional `cognitive_delegate` parameter:

```python
class FlowExecutor:
    def __init__(
        self,
        core_context: CoreContext,
        cognitive_delegate: CognitiveFlowDelegate | None = None,
    ) -> None:
        ...
        self._cognitive_delegate = cognitive_delegate
```

`FlowExecutor.execute()` replaces the single-pass params with accumulated threading:

```python
accumulated_params: dict[str, Any] = dict(params)
for step in definition.steps:
    step_result = await self._execute_step(
        step, write=write, caller_params=accumulated_params
    )
    step_results.append(step_result)

    # Thread step outputs into downstream params.
    # Fail loudly if a declared produces key is absent from the output —
    # silent continuation would let the write step receive None for generated_code.
    if step_result.ok and step.produces:
        output = step_result.data if isinstance(step_result.data, dict) else {}
        missing = [k for k in step.produces if k not in output]
        if missing:
            logger.error(
                "FlowExecutor: cognitive step '%s' did not produce declared "
                "key(s) %s — halting flow",
                step.ref_id, missing,
            )
            step_result = StepResult(
                ref_id=step.ref_id, required=step.required, ok=False,
                data={"error": "missing_produces_keys", "missing": missing},
                duration_sec=step_result.duration_sec, kind=step.kind.value,
            )
        else:
            for key in step.produces:
                accumulated_params[key] = output[key]

    if not step_result.ok and step.required:
        ...  # halt as before
```

`FlowExecutor._execute_step()` routes `StepKind.COGNITIVE` to a new
`_execute_cognitive_step()` method:

```python
async def _execute_cognitive_step(
    self, step: FlowStep, params: dict[str, Any], step_start: float
) -> StepResult:
    if self._cognitive_delegate is None:
        logger.error(
            "FlowExecutor: cognitive step '%s' encountered but no "
            "CognitiveFlowDelegate was injected — flow cannot proceed",
            step.ref_id,
        )
        return StepResult(
            ref_id=step.ref_id, required=step.required, ok=False,
            data={"error": "no_cognitive_delegate"},
            duration_sec=time.time() - step_start, kind="cognitive",
        )
    try:
        output = await self._cognitive_delegate.execute_cognitive_step(
            step_ref=step.ref_id, params=params
        )
        return StepResult(
            ref_id=step.ref_id, required=step.required, ok=True,
            data=output,
            duration_sec=time.time() - step_start, kind="cognitive",
        )
    except Exception as exc:
        ...  # log and return failure StepResult
```

The `write` flag is NOT passed to cognitive steps — generation is always a read/think
operation. The mutation gate lives exclusively in the write step.

### D5 — Will-tier cognitive implementation: `PromptModelIterativeAgent`

A new class `src/will/agents/prompt_model_iterative_agent.py` carries the generation
loop extracted from `build_test_for_symbol_action.py`:

```python
class PromptModelIterativeAgent:
    """
    Will-tier iterative generation agent for direct PromptModel.invoke() paths.

    Parallel to IterativeCoderAgent (which wraps CoderAgent for ExecutionTask-based
    flows). Use this agent when the generation path uses PromptModel.invoke() with
    custom context variables rather than CoderAgent's ContextService pipeline.

    The loop: generate → IntentGuard → feed violations back → repeat, up to the
    governed cap in generation_budget.yaml.
    """

    async def generate(
        self,
        prompt_name: str,
        repair_prompt_name: str,
        context: dict[str, Any],
        cognitive_service: CognitiveProtocol,
        repo_root: Path,
        task_type: str = "test_generation",
    ) -> str:
        """
        Returns the first generated code string that passes IntentGuard.
        Raises GenerationFailedError if the cap is exhausted without acceptance.
        """
        ...
```

The behavioral contract of the loop is preserved: same budget source
(`load_generation_budget().for_task_type(task_type)`), same prompts
(`context_aware_test_gen` / `context_aware_test_gen_repair`), same `IntentGuard`
acceptance condition, same failure semantics where practical. Moving the loop across
layers changes its constructor shape, error types, and test boundaries; the contract
is preserved, the implementation is not guaranteed byte-identical.

### D6 — `TestGenCognitiveDelegate` — Will-tier implementation of `CognitiveFlowDelegate`

A new class `src/will/agents/test_gen_cognitive_delegate.py` wires the protocol to the
`PromptModelIterativeAgent`:

```python
class TestGenCognitiveDelegate:
    """Implements CognitiveFlowDelegate for flow.build_test_for_symbol."""

    def __init__(self, core_context: CoreContext) -> None:
        self._core_context = core_context

    async def execute_cognitive_step(
        self, step_ref: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if step_ref == "generate.test_snippet":
            return await self._generate_test_snippet(params)
        raise CognitiveStepError(f"Unknown cognitive step: {step_ref!r}")

    async def _generate_test_snippet(self, params: dict[str, Any]) -> dict[str, Any]:
        # Extract symbol source code via AST utilities (shared/utils/test_gen_utils.py)
        # Run PromptModelIterativeAgent
        # Return {"generated_code": <accepted code>}
        ...
```

**Extension pattern for future flows:** each new cognitive capability gets its own
`CognitiveFlowDelegate` implementation. No global cognitive step registry is introduced
in this ADR. A central delegate registry (mapping `cognitive_capability` → delegate class)
is the natural next step; it is deferred until at least three independent delegate types
exist, consistent with CORE's registry-introduction precedent.

### D7 — `build.test_for_symbol` action narrowed to write-only

The action is reduced to its Body-legitimate responsibilities:

```python
async def action_build_test_for_symbol(
    source_file: str,
    symbol_name: str,
    symbol_kind: str,
    generated_code: str,        # REQUIRED — produced by generate.test_snippet cognitive step
    core_context: CoreContext,
    write: bool = False,
    **kwargs,
) -> ActionResult:
    """
    Write a generated pytest test function to the test file.

    Receives pre-generated, pre-validated code from the cognitive step.
    Performs one defensive IntentGuard validation pass before writing.
    No LLM calls. No prompt loading. No iterative loop.

    MUST only be invoked via flow.build_test_for_symbol. Direct invocation as a
    standalone action target is prohibited: no caller would supply generated_code.
    """
```

The `generation_mode` parameter is removed entirely. The action no longer has any concept
of generation strategy — that is the caller's concern.

**Removed from the action:**
- `PromptModel` import and usage
- `cognitive_service` acquisition and `aget_client_for_role()` call
- `load_generation_budget()` call
- The iterative loop (L214–391 in the original)
- `context_aware_test_gen` and `context_aware_test_gen_repair` prompt references
- `_extract_symbol_code()` — moved to `TestGenCognitiveDelegate` (pure prompt-grounding,
  not a write concern; it feeds `symbol_code` into the LLM context, L170–172)
- `remediates` decorator annotation — moved to the flow manifest (D8)

**Retained:**
- `source_to_test_path()` path resolution
- One `IntentGuard.validate_generated_code()` call (defensive gate on received artifact)
- `FileHandler` write + `__init__.py` ancestor seeding

### D8 — `flow.build_test_for_symbol.yaml` updated

`generation_mode` is promoted from a step-level action parameter to a flow-level field.
`FlowDefinition.generation_mode` and its loader already exist in `FlowRegistry`
(`registry.py` L100 for the field, L160 for the parse, L226 for construction);
no new loader change is required for that field. The step-level
`params: {generation_mode: iterative}` is removed. A new `cognitive_capability` field
(D9) is added for delegate routing.

The `remediates` annotation is moved here from the action: the flow — not the bare
write action — is what remediates `test.runner.missing` and `test.runner.failure`.

```yaml
generation_mode: iterative       # promoted from step param; governs strategy inside delegate
cognitive_capability: test_generation  # governs delegate selection in ProposalExecutor (D9)

flow:
  flow_id: flow.build_test_for_symbol
  remediates: [test.runner.missing, test.runner.failure]
  ...
  steps:
    - ref_id: generate.test_snippet
      kind: cognitive
      required: true
      consumes: [source_file, symbol_name, symbol_kind, signature]
      produces: [generated_code]

    - ref_id: build.test_for_symbol
      kind: action
      required: true
      consumes: [source_file, symbol_name, symbol_kind, generated_code, write]
      # params.generation_mode removed — no longer applicable

    - ref_id: fix.imports
      kind: action
      required: false
      consumes: [write]

    - ref_id: fix.headers
      kind: action
      required: false
      consumes: [write]

    - ref_id: fix.format
      kind: action
      required: false
      consumes: [write]

    - ref_id: test.sandbox_validate
      kind: action
      required: true
      consumes: [source_file]
```

### D9 — `ProposalExecutor` injects the cognitive delegate

Routing MUST use `cognitive_capability`, not `generation_mode`. `generation_mode` is a
strategy selector that lives inside the delegate; `cognitive_capability` identifies which
delegate to construct. This distinction prevents routing ambiguity when multiple
capabilities share the same generation strategy.

`FlowDefinition` gains a new field:

```python
cognitive_capability: str | None = None
"""
Capability identifier for CognitiveFlowDelegate selection (ADR-140 D9).
None = no cognitive steps in this flow.
"""
```

`FlowRegistry._load_entry` reads it alongside `generation_mode`:

```python
cognitive_capability = data.get("cognitive_capability") or None
```

`ProposalExecutor._build_cognitive_delegate()` routes by `cognitive_capability`:

```python
from body.flows.registry import flow_registry, StepKind
from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate

def _build_cognitive_delegate(
    self, flow_id: str, scoped_context: CoreContext
) -> CognitiveFlowDelegate | None:
    """Return the appropriate CognitiveFlowDelegate for this flow, or None."""
    flow_def = flow_registry.get(flow_id)
    if not flow_def:
        return None
    has_cognitive = any(s.kind == StepKind.COGNITIVE for s in flow_def.steps)
    if not has_cognitive:
        return None
    # Route by cognitive_capability, not generation_mode.
    # generation_mode is a strategy selector; cognitive_capability names the delegate.
    cap = flow_def.cognitive_capability
    if cap == "test_generation":
        return TestGenCognitiveDelegate(scoped_context)
    logger.error(
        "ProposalExecutor: no delegate registered for cognitive_capability=%r "
        "in flow %r — cognitive steps will fail",
        cap, flow_id,
    )
    return None

# In the flow execution block:
cognitive_delegate = self._build_cognitive_delegate(ref_id, scoped_context)
flow_executor = FlowExecutor(scoped_context, cognitive_delegate=cognitive_delegate)
```

This is the single wiring point. `ProposalExecutor` is Will-tier and may import Will-tier
delegates; `FlowExecutor` (Body) never does.

### D10 — Regression test: static boundary assertion

`tests/body/atomic/test_build_test_for_symbol_boundary.py`:

```python
def test_action_does_not_cross_cognitive_boundary():
    """Body write action must not load prompts, acquire cognitive clients, or import Will."""
    import ast
    import importlib.util
    from pathlib import Path

    spec = importlib.util.find_spec("body.atomic.build_test_for_symbol_action")
    source = Path(spec.origin).read_text()
    tree = ast.parse(source)

    # Check ast.Name references (direct name use)
    forbidden_names = {"PromptModel", "aget_client_for_role", "load_generation_budget"}
    names_used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not (forbidden_names & names_used), (
        f"Body write action references cognitive names: {forbidden_names & names_used}"
    )

    # Check attribute access (e.g. core_context.cognitive_service)
    forbidden_attrs = {"cognitive_service", "aget_client_for_role"}
    attrs_used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    assert not (forbidden_attrs & attrs_used), (
        f"Body write action accesses cognitive attributes: {forbidden_attrs & attrs_used}"
    )

    # Check imports — no will.* and no shared.infrastructure.llm imports
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = (
                node.module if isinstance(node, ast.ImportFrom) else None
            ) or ""
            for alias in getattr(node, "names", []):
                full = f"{module}.{alias.name}" if module else alias.name
                assert not full.startswith("will."), (
                    f"Body write action imports from will layer: {full}"
                )
                assert "shared.infrastructure.llm" not in full, (
                    f"Body write action imports LLM infrastructure: {full}"
                )


def test_action_requires_generated_code_parameter():
    """Body write action must declare generated_code as a required parameter."""
    import inspect
    from body.atomic.build_test_for_symbol_action import action_build_test_for_symbol

    sig = inspect.signature(action_build_test_for_symbol)
    assert "generated_code" in sig.parameters
    param = sig.parameters["generated_code"]
    assert param.default is inspect.Parameter.empty, (
        "generated_code must be required (no default) — "
        "it is produced by the cognitive step, not caller-supplied"
    )
```

---

## Blueprint rule for future flows requiring LLM generation

Any future CORE flow that requires LLM generation MUST follow this pattern:

1. **Declare `cognitive_capability`** in the flow manifest (e.g. `test_generation`,
   `doc_generation`). This is the delegate routing key.
2. **Declare `generation_mode`** in the flow manifest (e.g. `iterative`, `single_shot`).
   This is the strategy selector, read by the delegate internally.
3. **Declare a `kind: cognitive` step** for the generation phase, with `produces` listing
   the generated artifact key(s).
4. **Declare a `kind: action` step** for the write phase, with `consumes` including the
   generated artifact key(s).
5. **Move `remediates` to the flow manifest**, not the action decorator — the flow, not
   the bare write action, is what closes the blackboard finding.
6. **Author a `CognitiveFlowDelegate` implementation** in `src/will/agents/` for the
   generation step(s).
7. **Register the delegate** in `ProposalExecutor._build_cognitive_delegate()` by
   `cognitive_capability` value.
8. **Body action receives artifact as required param.** No prompt loading, no cognitive
   client access, no `_extract_symbol_code`-style prompt-grounding utilities. At most one
   validation pass on the received artifact.
9. **Add a regression test** asserting the Body action has no cognitive boundary crossings
   (D10 template).

The `CognitiveFlowDelegate` protocol (`shared/protocols/cognitive_flow_delegate.py`) is the
stable contract. Its implementations may change; the contract may not without an ADR.

---

## What this ADR does not decide

- **`IterativeCoderAgent` for other flows.** `IterativeCoderAgent` wraps `CoderAgent` for
  `ExecutionTask`-based flows. It remains the correct primitive for flows that route through
  `CoderAgent.generate_or_repair`. `PromptModelIterativeAgent` (D5) is the parallel for
  direct `PromptModel.invoke()` paths. The two coexist; neither deprecates the other.
- **Parallelism within cognitive steps.** Each cognitive step is sequential. Parallel
  generation strategies are a separate capability.
- **Extension of `StepKind.COGNITIVE` to other generation tasks.** The pattern is
  established here for test generation. Generalisation to source-file modification,
  documentation, or schema inference requires its own `CognitiveFlowDelegate` and is a
  separate ADR.
- **A global delegate registry.** No such registry is introduced here. A registry mapping
  `cognitive_capability` → delegate class is the natural evolution once ≥3 delegate types
  exist. Until then, `ProposalExecutor._build_cognitive_delegate()` is the routing table.

---

## Implementation sequence

Each step is independently reviewable. Steps 1–4 introduce no behavioural change to the
live pipeline; Step 8 is the activation gate (narrowing the action).

1. `shared/protocols/cognitive_flow_delegate.py` — new protocol (D3)
2. `shared/utils/test_gen_utils.py` — extract pure AST utilities from action (D7)
3. `body/flows/registry.py` — `StepKind.COGNITIVE`, `FlowStep.produces`,
   `FlowDefinition.cognitive_capability` field + loader (D2, D9)
4. `body/flows/executor.py` — cognitive routing, `produces` key validation,
   inter-step threading, DI constructor (D4)
5. `will/agents/prompt_model_iterative_agent.py` — new Will-tier agent (D5)
6. `will/agents/test_gen_cognitive_delegate.py` — new Will-tier delegate (D6)
7. `will/autonomy/proposal_executor.py` — inject delegate via `_build_cognitive_delegate` (D9)
8. `body/atomic/build_test_for_symbol_action.py` — narrowed to write-only (D7)
9. `.intent/flows/flow.build_test_for_symbol.yaml` — updated steps + `cognitive_capability` (D8)
10. `tests/body/atomic/test_build_test_for_symbol_boundary.py` — regression test (D10)
11. Update `IterativeCoderAgent` architecture note — close the documented debt

Note: `FlowDefinition.generation_mode` and its loader already exist in `registry.py`
(field L100, parse L160, construct L226). Step 3 adds `FlowDefinition.cognitive_capability`,
`FlowStep.produces`, and the corresponding loader lines for both; no duplicate work on
`generation_mode`.

---

## Consequences

### Positive
- **Body actions are constitutionally clean.** No LLM infrastructure in mutation code.
  Fully testable in isolation; deterministic under any cognitive layer state.
- **Cognitive orchestration is fully Will-tier.** The loop, prompt selection, repair logic,
  and acceptance condition live where they belong.
- **Reusable pattern.** Any future flow with LLM generation follows D1–D10 without
  architectural debate. The blueprint is law.
- **FlowExecutor stays Body.** No layer boundary crossed. The DI protocol ensures Body
  never knows about Will implementations.
- **Regression tests enforce the boundary.** Static assertions catch regressions before
  they reach CI; no runtime is needed.
- **`produces` key validation fails loudly.** A cognitive step that claims to produce
  `generated_code` but doesn't will halt the flow rather than silently feeding `None` into
  the write action.

### Negative
- **More moving parts.** A flow that previously had one action step now has one cognitive
  step + one write step + a delegate class. The cognitive loop is no longer co-located with
  the write code.
- **`ProposalExecutor` delegate routing grows over time.** Each new cognitive capability
  adds a branch to `_build_cognitive_delegate`. A delegate registry (mapping
  `cognitive_capability` → delegate class) is the natural evolution; deferred until ≥3
  delegate types exist.
- **Cognitive steps are not sandboxed independently.** The entire flow (including the
  cognitive step) runs in the same sandbox context. The cognitive step produces a string
  in memory; no isolation is lost. Explicitly noted here to avoid future confusion.

### Neutral
- **`IterativeCoderAgent` remains as-is.** Its architecture note is updated to reflect
  that the debt is closed. `PromptModelIterativeAgent` is a sibling, not a replacement.
- **`generation_mode` field on `FlowDefinition` gains operational meaning.** Previously
  metadata-only (D5 was never implemented). Now read by delegates to select generation
  strategy. `cognitive_capability` — added by this ADR — governs delegate selection.
- **`_extract_symbol_code` moves from action to delegate.** It was prompt-grounding
  utility that had no business being in a write-only action.

---

## References

**ADRs:**
- ADR-135 D1 — dual-mode generation primitives (this ADR closes D5)
- ADR-133 D3/D7 — symbol-granular test generation; `build.test_for_symbol` contract
- ADR-106 — hermetic worktree per flow execution (sandbox context unchanged)
- ADR-017 D4 — `ActionExecutorProtocol` as the Will→Body DI pattern this ADR mirrors

**Rules:**
- `architecture.boundary.llm_client_access` (blocking) — primary driver
- `architecture.layers.no_body_to_will` (reporting) — DI pattern resolves this
- `architecture.flows.atomic_action_must_not_compose` — why Will → Body routing via
  DI is the only clean path (actions cannot call other actions)

---

## Amendment 2026-07-13 — pytest belongs in the acceptance loop: wiring ADR-135 D6 onto the D5 generation path

**Status:** Accepted (decision) — implementation **deferred by intent** pending evidence
**Tracking:** #791

### Implementation status — deferred by intent (2026-07-13)

This amendment records an accepted *decision*, not a completed change. Implementation is
deliberately deferred, and that deferral is put on paper here so it reads as a **known,
triggered decision — not silent drift** (the exact failure mode that produced the D6 gap
in the first place).

Why deferred: the static-context fixes shipped 2026-07-13 (dotted-method, mock-target,
constructor, and module-constant extraction — #791 lineage) already lifted the generator's
hit rate, and every one of them fixed the generator for *all future files*, cheaply and
without touching the autonomous generation path. The pytest-in-the-loop rewire is a
different cost class: multi-file, high blast radius (it changes the daemon's core
generation loop and could regress files that now pass), and justified so far only by a
small **manually-driven** generation sample — not by the *daemon's* measured behaviour.
Spending it now would be optimising ahead of evidence.

**Re-evaluation trigger:** let the daemon run the improved (static-fix) pipeline against
the live remediation backlog, then measure the residual runtime-contract failure rate.
Implement the change-set below only if that rate justifies the rewire cost. If the residual
is instead dominated by integration-shaped workers (ones that genuinely need a real
`declaration_name` declaration or DB wiring to test), the boring answer is to exclude those
from autonomous *unit*-test-gen scope (`include_files` in `test_coverage.yaml`) rather than
grow the generator — a one-line decision, not a pipeline rewire.

The decision below (D6 stands; here is the correct wiring) is recorded now so it is not
re-derived from scratch later; the *when* is gated on the trigger above.

### The gap

ADR-135 D6 (accepted) prescribed that `flow.build_test_for_symbol`'s acceptance
condition be `CompositeAcceptanceCondition([PytestAcceptanceCondition,
AuditAcceptanceCondition])` — pytest run *inside* the iterative generate→validate→repair
loop, so a test that imports cleanly but fails at runtime feeds its failure back as the
repair signal. This is the exact exit gate whose **10/10 recovery rate** the ADR-135 spike
evidence rests on.

This ADR (140) then introduced `PromptModelIterativeAgent` (D5) as the cognitive-write-
separation vehicle for that flow. In doing so it inadvertently dropped D6's acceptance
wiring: `PromptModelIterativeAgent.generate()` hardcodes a single static gate
(`intent_guard.validate_generated_code`) as its only accept/reject check, and pytest was
left as a *separate, post-loop* flow step (`test.sandbox_validate`, `required: true`).
Consequence: a sandbox/runtime failure fails the whole flow instead of driving a repair
iteration. The richest signal the iterative loop exists to exploit — "does the generated
test actually run?" — is excluded from the loop.

Verified on disk 2026-07-13 (#791):

- `src/will/agents/acceptance/conditions.py` contains the `AcceptanceCondition` protocol,
  `IntentGuardAcceptanceCondition`, `PytestAcceptanceCondition`, and
  `CompositeAcceptanceCondition` — but nothing imports or wires them into the live
  generation path.
- `AuditAcceptanceCondition` (named in D6's literal composite) **was never built**.
- `PytestAcceptanceCondition.evaluate` is **incomplete**: it receives `code` but never
  writes it before validating (calls `test.sandbox_validate` with `write=False` against
  whatever is already on disk).
- **No tests** reference any acceptance-condition class.
- The `task: ExecutionTask` parameter on `AcceptanceCondition.evaluate` is **unused by all
  three implementations** — a vestige of ADR-135's `ExecutionTask`-based `IterativeCoderAgent`
  design that does not fit ADR-140's context-dict + `target_path` `PromptModelIterativeAgent`.

This is a textbook "closed-by-ADR ≠ closed-by-evidence": the decision was accepted, the
parts were ~two-thirds built, then the live path was rerouted and the wiring rotted
unwired and untested. This amendment fixes it.

### Decision

1. **ADR-135 D6 stands — pytest belongs inside the acceptance loop, not after it.**
   Rationale: (a) it is the only position with evidence (the 10/10 spike); (b) the
   iterative loop's entire value is feedback richness, and runtime execution is the
   richest signal; (c) the empirically-observed remaining failure class (worker
   `declaration_name` contract, unmocked session factory — #791) is *only* catchable by a
   runtime signal, not by static analysis; (d) the layer concern is already resolved —
   `PytestAcceptanceCondition` delegates to Body via `ActionExecutor.execute
   ("test.sandbox_validate")`, so Will never runs a subprocess.

2. **ADR-140's cognitive-write separation structure stands; this amendment completes it,
   it does not revert it.** The D5 reroute through `PromptModelIterativeAgent` was correct
   for the `architecture.boundary.llm_client_access` concern (LLM call out of Body). It
   dropped D6's acceptance wiring as *collateral*, not as a deliberate rejection.
   `PromptModelIterativeAgent` remains the canonical test-generation path;
   `IterativeCoderAgent` is unchanged.

3. **The loop consumes an injected `AcceptanceCondition` instead of a hardcoded static
   gate.** `PromptModelIterativeAgent.generate()` accepts an `AcceptanceCondition` (default
   for test-gen: `CompositeAcceptanceCondition([IntentGuardAcceptanceCondition,
   PytestAcceptanceCondition])`). On rejection, the condition's `violation_summary`
   becomes the repair-prompt feedback — the identical mechanism the hardcoded IntentGuard
   violations use today, so the repair contract is unchanged; only the *source* of
   violations widens from static-only to static+runtime.

4. **Deviation from D6's literal composite, stated explicitly.** The target composite is
   `[IntentGuardAcceptanceCondition, PytestAcceptanceCondition]`, **not** the D6-literal
   `[PytestAcceptanceCondition, AuditAcceptanceCondition]`. Reasons: `AuditAcceptanceCondition`
   was never built and shells out to `core-admin code audit` (heavier, a subprocess);
   `IntentGuardAcceptanceCondition` already provides the equivalent static-governance check
   in-process and is exactly what the live loop uses today. So the minimal, boring target is
   "keep today's static check + add the missing runtime check." Order matters and is
   deliberate: IntentGuard first (cheap, in-process), Pytest second (expensive, subprocess)
   — `CompositeAcceptanceCondition` short-circuits on first failure, so a statically-broken
   candidate never reaches pytest. `AuditAcceptanceCondition` remains deferred/unbuilt; if a
   future flow needs the full offline-audit gate, it is added then.

5. **The impedance mismatch is resolved by dropping the unused `task: ExecutionTask`
   parameter** from `AcceptanceCondition.evaluate` (verified unused by all three
   implementations). Per-condition configuration stays constructor-injected
   (`target_path`, `source_file`, `executor`, `repo_root`). No `ExecutionTask` adapter is
   invented; the protocol is adapted to what the `PromptModelIterativeAgent` path can
   actually supply (the generated `code` string).

6. **`PytestAcceptanceCondition` is completed** so it writes `code` to the sandbox target
   (via the injected `FileHandler`, or by ordering behind `build.test_for_symbol`) before
   invoking `test.sandbox_validate` — today it validates stale on-disk content and ignores
   its own `code` argument.

7. **`test.sandbox_validate` as a post-loop flow step becomes redundant on the happy path**
   once the loop validates the accepted candidate. Removing it is *optional and out of
   scope for this decision* — the load-bearing decision is pytest-in-the-loop. It may be
   kept as a final belt-and-suspenders gate against the actually-written file, or removed
   in a follow-up; either is compatible with this amendment.

8. **A fitness function guards the decision going forward.** Once wired, a reporting-posture
   rule asserts the observable property — the test-generation acceptance path includes a
   sandbox-execution gate — so this cannot silently drift again. The *absence* of exactly
   this enforcement at D6 acceptance time is the root cause of the drift this amendment
   repairs: an accepted decision that claimed a runtime behavior was never encoded as
   enforced data. Encoding it is the boring-consistency fix; the meta-lesson (ADR decisions
   claiming a runtime behavior should carry an enforcement link before they are treated as
   closed) is noted for the governance process but is a larger call left to a separate ADR.

### Change-set (when implemented — gated on the re-evaluation trigger above)

- `src/will/agents/acceptance/conditions.py`: drop unused `task` param from the protocol
  and the three `evaluate` signatures; complete `PytestAcceptanceCondition` to write `code`
  before validating.
- `src/will/agents/prompt_model_iterative_agent.py`: accept an injected
  `AcceptanceCondition`; replace the hardcoded `intent_guard.validate_generated_code` block
  with `condition.evaluate(code)`; map its `AcceptanceResult` onto the existing
  violation-feedback path.
- `src/will/agents/test_gen_cognitive_delegate.py`: construct
  `CompositeAcceptanceCondition([IntentGuardAcceptanceCondition, PytestAcceptanceCondition])`
  with the executor + `target_path` + `source_file` and inject it.
- Tests: acceptance conditions (currently zero coverage) and the wired loop, including a
  case proving a runtime-only failure (imports clean, fails at run) drives a repair
  iteration.
- Add the fitness-function rule (decision 8).

### Consequences

Positive: the failure class that static analysis cannot see (runtime contracts —
`declaration_name`, session factory, wrong mock target that only fails on execution)
becomes self-correcting inside the governed iteration budget, restoring the spike's
measured recovery behavior. Negative: pytest runs per rejected iteration rather than once,
within the already-governed `generation_budget.yaml` cap (`max_iterations`,
`wall_clock_cap_secs`) — the cost the spike already accepted for its payoff.

---

## Status note 2026-07-14 — the deferral trigger fired NO on measured evidence

**Status:** The Amendment 2026-07-13 change-set (pytest-in-the-loop rewire) stays
**deferred — now on measured evidence, not merely on intent.** Tracking: #791.

The amendment deferred implementation behind a re-evaluation trigger: *let the improved
pipeline run against the backlog, measure the residual runtime-contract failure rate, and
implement only if it justifies the (high-blast-radius) rewire.* That measurement was run
2026-07-14 (governor-authorised offline harness exercising CORE's own
`flow.build_test_for_symbol` path — `TestGenCognitiveDelegate` + the 2026-07-13 static
fixes — at HEAD `e9006ff9`, one hermetic worktree per symbol; the daemon could not measure
itself because all pilot files were sitting `remediation_cap_reached`/`abandoned`).

**Result (16 symbols that had failed pre-fix, first-attempt condition):**

- **PASS 9/16 (56%)** — including the cap-abandoned *integration-shaped* workers the
  amendment named as the "exclude, don't grow the generator" population
  (`CapabilityTaggerWorker`, `RepoEmbedderWorker.run`, `DbSyncWorker.run`,
  `RepoCrawlerWorker.run` all green).
- **runtime-contract `declaration_name` / session-factory: 0/16.** The exact failure class
  D6 was justified to catch — the one only a runtime signal can see and static analysis
  cannot — is **empty** post-fix. The cheap static-context fixes (constructor / module-const
  / mock-target extraction) converted it.
- runtime-contract `mock target`: 2/16; generic runtime assertion/other: 5/16; static gate: 0/16.

**Conclusion.** The residual does not justify the rewire. Neither branch of the trigger
fires cleanly: the population D6 uniquely serves is gone, and the "exclude integration
workers" branch is moot because those workers now pass. The Amendment 2026-07-13 change-set
(§Change-set) is therefore **not implemented and not re-queued**; D6-in-the-abstract still
"stands" as the correct shape *were* the runtime-contract residual to grow, but there is no
current evidence to act on. **Decision 8 (the fitness-function drift-guard) remains worth
doing cheaply and independently** of the rewire, so the acceptance path's shape stays
legible.

**What the measurement surfaced instead (#792).** The dominant *reproducible* failure was
not a cognitive gap but a plain pipeline bug: `build.test_for_symbol` appends a snippet whose
mandated leading `from __future__ import annotations` then lands mid-file → `SyntaxError` at
collection. Bounded fix, higher throughput payoff than the rewire; tracked separately as #792.

---

## Status note 2026-07-14 (later) — trigger re-fires GO after #792; change-set corrected and implemented

**Status:** Accepted (decision) — **implemented this session.** Tracking: #791.

#792 landed after the NO-GO note above was written. Re-measuring on the real (fixed) append
path, n=16 previously-failed symbols: **7/16 pass, 0 static/collection failures.** The 9-symbol
residual is dominated by **async/mock-contract failures** — `coroutine object has no attribute
'first'` (async call not awaited), `assert_awaited_once_with` against a plain `MagicMock`
instead of `AsyncMock`, item-assignment on a `MagicMock`, mock-call-signature mismatches, a
hallucinated `pytest.helpers` API. This is a different failure shape than the
`declaration_name`/session-factory population the morning NO-GO measured (which the static
fixes had already emptied) — but it is the same *category*: only a runtime execution signal
distinguishes "imports cleanly" from "actually passes," and static analysis (IntentGuard)
cannot see it.

**Disposition: GO.** The trigger's condition — "implement only if the residual runtime-contract
failure rate justifies the rewire" — is met by this new population. Decisions 1–8 above stand
as written and are now implemented, with two corrections surfaced during implementation
reconnaissance that the original change-set did not account for:

**Correction A — a second, unlisted caller of `AcceptanceCondition.evaluate`.**
`IterativeCoderAgent.generate_until_accepted` (`src/will/agents/iterative_coder_agent.py`,
ADR-135 D2) already calls `acceptance.evaluate(code, task)` with a live `ExecutionTask`. Decision
5's "drop the unused `task` parameter" is correct — no implementation reads it — but the change
is only safe once this call site is also updated to `acceptance.evaluate(code)`. Added to the
change-set: `iterative_coder_agent.py` is a 4th file, alongside `conditions.py`,
`prompt_model_iterative_agent.py`, and `test_gen_cognitive_delegate.py`.

**Correction B — decision 6's "either/or" write options are not equivalent.** Decision 6 allowed
completing `PytestAcceptanceCondition` either "via the injected FileHandler, or by ordering
behind `build.test_for_symbol`." The second option is unsafe as stated: `build.test_for_symbol`'s
`write=True` path **appends** the candidate snippet to existing file content (ADR-133/#792
behavior, intentionally preserved for the real single production write). Calling that action once
per loop iteration would leave every rejected candidate's body permanently appended, with each
repair attempt's candidate stacking on top instead of replacing it — a corruption mode, not a
neutral implementation choice. Corrected design: `TestGenCognitiveDelegate` captures the test
file's pre-loop base content once, injects it into `PytestAcceptanceCondition`, which recomputes
`base + candidate` fresh and **overwrites** (never appends) on every `evaluate()` call, via
`CoreContext.file_service` (ADR-097 D4) — the sanctioned Will-tier write door built specifically
so Will consumers do not touch `FileHandler` directly. No new boundary debt: `file_service` is
already the correct injection point for this, simply not yet used by this code path. The real,
single, append-based production write is unchanged: it still happens exactly once, after
acceptance, via the flow's own `build.test_for_symbol` step.

Both corrections are refinements of the already-accepted decision, not new architectural
calls — no protocol shape, layering, or trigger logic changes as a result.
