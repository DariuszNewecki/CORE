# Changelog

All notable changes to this project are documented in this file.

This project follows **Keep a Changelog** and **Semantic Versioning**, but with an explicit focus on **governance maturity and autonomy progression**, not just features.

---

## [2.2.0] — 2026-01-08

### 🎯 Universal Workflow Pattern — The Operating System

This release establishes the **foundational architecture for autonomous operations at scale**. CORE now has a universal orchestration model that closes all loops, enables self-correction everywhere, and provides the substrate for fully autonomous conversational operation.

This is the **conceptual breakthrough** that makes CORE an operating system for AI-driven development, not just a collection of tools.

### Philosophy Shift

**Before 2.2.0**: Collection of autonomous capabilities with ad-hoc orchestration
**After 2.2.0**: Universal workflow pattern that composes all operations

### Added

#### Constitutional Architecture

* **INTERPRET Phase — 6th Constitutional Phase** (2026-01-15)
  - Elevated intent interpretation to constitutional primitive
  - First phase in governance pipeline (INTERPRET → PARSE → LOAD → AUDIT → RUNTIME → EXECUTION)
  - Completes Mind-Body-Will architecture (Will layer now has constitutional entry point)
  - Dynamic phase discovery from `.intent/phases/*.yaml` (zero hardcoding)
  - Paper: `.intent/papers/CORE-Phases-as-Governance-Boundaries.md` (updated to 6 phases)
  - Implementation: `InterpretPhase` v1 (deterministic pattern matching)
  - Evolution path documented: v1 (deterministic) → v2 (LLM-assisted)
  - All 3 workflows updated to start with INTERPRET phase
  - 100% test pass rate (8/8 phase verification + 5/5 workflow inference tests)

* **Dynamic Phase Registry** (2026-01-15)
  - Phase discovery from constitutional definitions, not hardcoded imports
  - Constitution → Implementation (proper governance direction)
  - Minimal hardcoding: single PHASE_IMPLEMENTATIONS registry
  - Automatic validation that phases have implementations
  - Clear migration path for stub → real phase implementations

* **Universal Workflow Pattern** (`.intent/papers/CORE-Adaptive-Workflow-Pattern.md`)
  - Canonical pattern: INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE
  - Constitutional phases: INTERPRET, PARSE, LOAD, AUDIT, RUNTIME, EXECUTION
  - TERMINATE boundary separates generation from finalization
  - Conceptual decision points replace magic numbers

#### Component Types Formalized

* **Interpreters** (INTERPRET phase) - Parse intent → canonical task structure
  - Foundation for conversational interface (`core` CLI)
  - Natural language and structured input support
  - *Status: Documented, implementation pending*

* **Analyzers** (PARSE phase) - Extract structural facts without decisions
  - FileAnalyzer: Classify file types and complexity
  - SymbolExtractor: Find testable functions and classes
  - *Existing: 2 implemented, 3 planned*

* **Evaluators** (AUDIT phase) - Assess quality and identify patterns
  - FailureEvaluator: Test failure pattern recognition
  - ClarityEvaluator: Cyclomatic complexity measurement
  - *Existing: 2 implemented, 3 planned*

* **Strategists** (RUNTIME phase) - Make deterministic decisions
  - TestStrategist: Select test generation strategy with adaptive pivots
  - ClarityStrategist: Choose refactoring approach
  - *Existing: 2 implemented, 3 planned*

* **Orchestrators** (RUNTIME phase) - Compose components into adaptive workflows
  - ProcessOrchestrator: Generic component sequencer
  - AdaptiveTestGenerator: Test generation with failure recovery (70-80% success)
  - ClarityServiceV2: Refactoring with recursive self-correction
  - AutonomousWorkflowOrchestrator: Three-phase development workflow
  - DevSyncWorkflow: Multi-action fix-sync pipeline
  - *Existing: 5 operational*

#### Adaptive Workflow Features

* **Self-Correcting Loops** - Pattern-based adaptation
  - "Did result improved?" - Relative quality assessment
  - "SOLVED?" - Multi-dimensional quality gate (syntax + tests + constitutional + improvement)
  - "Continue trying?" - Holistic termination evaluation (time, attempts, confidence, stuck detection)

* **Decision Tracing** - Full audit trail of autonomous decisions
  - DecisionTracer integration mandatory for strategic choices
  - Pattern history tracking for learning
  - Strategy pivot rationale recording

* **Component Discovery** - Runtime introspection
  - Registry-based (Atomic Actions)
  - Convention-based (Components)
  - Service Registry (Infrastructure)

### Changed

#### Interface Clarity

* **`core` CLI** - Positioned as primary conversational interface
  - Natural language → autonomous operation
  - "Please do X" → CORE figures out how
  - Foundation for web/API interfaces
  - *Status: Exists, needs workflow integration*

* **`core-admin` CLI** - Positioned as developer tooling
  - Direct, explicit control of internals
  - Surgical tools for maintaining CORE itself
  - *Status: Stable, needs pattern compliance*

#### Architecture

* **Component Phases** - Strict constitutional boundaries
  - INTERPRET: Understand user intent (new)
  - PARSE: Extract structure (formalized)
  - LOAD: Retrieve data (formalized)
  - AUDIT: Evaluate quality (formalized)
  - RUNTIME: Make decisions (formalized)
  - EXECUTION: Mutate state (existing)

* **ComponentResult Contract** - Universal return structure
  ```python
  @dataclass
  class ComponentResult:
      component_id: str
      ok: bool
      data: dict[str, Any]
      phase: ComponentPhase
      confidence: float  # 0.0-1.0 for workflow routing
      next_suggested: str  # Hint for adaptive workflows
      metadata: dict[str, Any]
      duration_sec: float
  ```

#### Workflow Patterns

* **V1 → V2 Migration Path** - Clear refactoring strategy
  - Checkers → Evaluators (consistent interface)
  - Builders → Analyzers (phase boundary compliance)
  - Legacy workflows → Orchestrator compositions
  - Procedural code → Component compositions

### Fixed

* **Conceptual Clarity** - Long-term vision documented
  - Three interfaces (core, core-admin, API/web)
  - Component lifecycle patterns
  - Constitutional compliance requirements
  - Integration points

* **Architectural Gaps** - Identified and prioritized
  - Missing RequestInterpreter (blocks conversational autonomy)
  - Insufficient Strategists (incomplete decision coverage)
  - Insufficient Evaluators (incomplete quality gates)

### Patterns Established

#### Existing V2 Commands

* ✅ `core-admin coverage generate-adaptive` - Test generation with adaptive learning
* ✅ `core-admin fix clarity` - Clarity refactoring with complexity evaluation
* 🔄 11 commands pending migration

#### Anti-Patterns Documented

* ❌ Bypassing Evaluators - Accepting LLM output without validation
* ❌ Direct Mutations - Writing files without ActionExecutor
* ❌ Missing Tracing - Strategic decisions without DecisionTracer
* ❌ Fixed Strategies - No adaptation to failure patterns
* ❌ Implementation-Detail Decisions - Checking counters instead of conceptual questions
* ❌ Imperative Flow - if/else chains instead of component composition
* ❌ Missing TERMINATE Boundary - Not separating generation from finalization

### Performance & Metrics

**Component Coverage**:
- Interpreters: 0/3 needed (critical gap)
- Analyzers: 2/5 needed
- Evaluators: 2/5 needed
- Strategists: 2/5 needed
- Orchestrators: 5/5 sufficient
- Atomic Actions: 10+ sufficient

**Command Migration**:
- Fully Migrated: 0 commands
- In Progress: 2 commands (15%)
- Not Started: 11 commands

**Overall Modernization**: ~12% complete

### What This Enables

#### Now

* **Conceptual Foundation** - Universal pattern for all autonomous operations
* **Component Library** - Reusable, composable building blocks
* **Self-Correction Model** - Adaptive loops with pattern learning
* **Clear Path Forward** - Roadmap from here to full autonomy

#### Soon (Next 3-5 Sessions)

* **RequestInterpreter** - Universal entry point for all commands
* **Complete Strategist Coverage** - Decisions for all operation types
* **Complete Evaluator Coverage** - Quality gates for all outputs
* **Pattern Compliance** - All commands follow universal workflow

#### Future (Natural Evolution)

* **Fully Autonomous `core` CLI** - Conversational interface that does what we do in this chat
* **Web Interface** - Same workflow, different transport
* **API Integration** - Programmatic access to all capabilities
* **Self-Replication** - CORE generates CORE.NG from intent (A4)

### Why This Matters

The Universal Workflow Pattern **closes all loops**:

1. **Self-Correction Everywhere** - Not command-specific, universally available
2. **Constitutional Governance** - Phase boundaries enforced at component level
3. **Autonomous Composition** - Any operation = component composition
4. **Traceable Decisions** - Full audit trail of strategic choices
5. **Scalable Architecture** - Same pattern from simple commands to full autonomy

Without this pattern:
- AI agents can't self-correct reliably
- Failures aren't traceable
- Constitutional governance is ad-hoc
- Code quality degrades over time

With this pattern:
- Every operation is self-correcting
- Every decision is traceable
- Every mutation is governed
- Quality improves autonomously

**The workflow closes all loops** - that's why this release is foundational.

### Migration Status

**Stable**: Constitutional governance, Atomic Actions, Component library exists
**Active**: Pattern compliance migration, Component gap filling
**Planned**: Full `core` conversational autonomy, Web/API interfaces

### Notes

* This release documents **conceptual architecture**, not feature completeness
* Migration is **incremental and safe** - old code remains until new is proven
* Success measured by **pattern compliance**, not feature count
* Autonomy advancement requires **workflow pattern adoption**, not just capability existence

---

## [2.1.0] — 2025-01 (Released)

### 🎯 Consolidation Release — Governance First

This release focused on **stabilisation, credibility, and enforcement depth**, rather than expanding raw capability. It represented the transition from *capability discovery* to *governance consolidation*.

### Added

#### Governance & Enforcement

* Enforcement coverage tracking promoted to **first-class governance signal**
* Explicit distinction between **declared vs enforced** constitutional rules
* Coverage regeneration and drift detection for governance audits
* Progressive disclosure output for enforcement results (CLI-first)

#### Autonomy Discipline

* Formalisation of **A2 Governed Autonomy** (coverage-bounded)
* Explicit autonomy ladder definitions embedded in documentation
* Clear separation between *capability existence* and *operational autonomy*

#### Documentation & Communication

* README rewritten for **credibility calibration** and human-friendly tone
* Clear articulation of *what CORE does not yet do*
* Alignment between metrics, autonomy claims, and enforcement scope

### Changed

* Reframed A2 status from "achieved" to **"governed and bounded"**
* Reduced implicit hype in public-facing descriptions
* Tightened language around autonomy, authority, and responsibility

### Removed

* Implicit assumptions that autonomy == coverage completeness

---

## [2.0.0] — 2024-11-28

### 🎯 Major Milestone: A2 Governed Code Generation (Foundational)

This release marked the **first operational realization of A2 autonomy**: the ability to autonomously generate new code under **constitutional governance**, with semantic awareness and enforced constraints.

This version established the **technical spine** of CORE.

### Added

#### Governed Code Generation (A2 — Foundational)

* **CoderAgent v1**: Context-aware autonomous code generation (70–80% success)
* **Semantic Infrastructure**: 500+ symbols vectorized, 60+ module anchors
* **Context Package System**: Structured, reproducible AI context construction
* **Semantic Placement**: Deterministic code placement accuracy
* **Policy Vectorization**: Agents reason semantically over constitutional rules
* **Architectural Context Builder**: System-wide structural awareness for agents
* **Module Anchors**: Semantic markers for placement and governance

#### Constitutional Governance

* **Constitutional Audit System**: Continuous validation with violation tracking
* **Micro-Proposal Loop**: Autonomous remediation proposals (governed)
* **Policy Coverage Service**: Mapping between rules and code regions
* **Agent Governance Policies**: Explicit autonomy lanes and prohibitions

#### Infrastructure & Runtime

* **Service Registry**: Deterministic lifecycle and dependency management
* **PostgreSQL Knowledge Graph**: Symbols and relations as SSOT
* **Vector Store Integration**: Semantic search over code and policies
* **Test Isolation**: Dedicated test database and execution paths

### Changed

#### Context & Reasoning

* Migration from ad-hoc string prompts to **structured ContextPackages**
* Architectural and policy context injected deterministically
* Improved reasoning traceability and reproducibility

#### Agent Behaviour

* Agents constrained to **explicitly permitted actions only**
* All AI output subject to constitutional validation
* Failure paths produce structured diagnostics

#### Quality & Validation

* Test generation improved through semantic awareness
* Governance checks integrated into standard workflows

### Fixed

* Dependency injection lifecycle inconsistencies
* Semantic placement drift
* Database session handling
* Import, header, and docstring compliance gaps

### Performance Signals (Indicative)

* Code generation success: ~70–80%
* Semantic placement accuracy: ~100%
* Knowledge graph growth: 0 → 500+ symbols

---

## [1.0.0] — 2024-10-01

### 🎯 Major Milestone: A1 Self-Healing Autonomy

Initial public release establishing **governed self-healing** as a first-class capability.

### Added

#### Self-Healing (A1)

* Autonomous docstring generation
* Header and metadata compliance
* Import organisation and formatting
* Policy-driven repair actions

#### Foundations

* Mind–Body–Will architecture
* Constitutional governance via `.intent/`
* Policy-driven validation model
* Initial agent framework

#### Tooling

* `core-admin` CLI
* Constitutional audit commands
* Autonomous repair workflows

---

## Autonomy Levels (Reference)

* **A0 — Self-Awareness**: Knowledge graph, symbol discovery
* **A1 — Self-Healing**: Autonomous compliance and drift repair
* **A2 — Governed Generation**: Code generation under enforced rules
* **A3 — Strategic Refactoring**: Multi-file architectural change (planned)
* **A4 — Self-Replication**: CORE generates CORE.NG from intent (conceptual)

---

### Notes

* Autonomy levels describe **operational behavior**, not theoretical capability.
* Advancement requires **measurable enforcement coverage**, not feature presence.
* Version 2.2.0 establishes the **architectural foundation** for A3 and beyond.

---

[2.2.0]: https://github.com/DariuszNewecki/CORE/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/DariuszNewecki/CORE/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/DariuszNewecki/CORE/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/DariuszNewecki/CORE/releases/tag/v1.0.0
