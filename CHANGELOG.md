# Changelog

All notable changes to this project are documented in this file.

This project follows **Keep a Changelog** and **Semantic Versioning**, but with an explicit focus on **governance maturity and autonomy progression**, not just features.

---

## [2.2.2] — 2026-02-28

### 🎯 Self-Compliance & Hygiene Edition

**Historic milestone**: CORE successfully governed its own major refactoring cycle with **zero constitutional violations** maintained throughout.

#### Changed
- Completed deep modularity refactoring (4 big files → 17 focused single-responsibility modules)
- Hardened Mind/Will/Body separation (fixed layer leaks, tracing exclusions, race conditions)
- Switched planning to deterministic `passive_gate` (no more unnecessary LLM calls)
- Unified `IntentGuard.check_transaction` API for cleaner constitutional validation
- Major repository hygiene cleanup (removed `.archive/`, binary/temp files, updated `.gitignore`)

#### Removed
- Legacy `.archive/` directory
- Temporary refactor cast files (`core-refactor.cast`)
- Any leftover sensitive or unnecessary files

#### Notes
- Real self-governance in action: the constitutional runtime actively flagged issues during development
- Technical debt reduced further, codebase now even cleaner and more maintainable
- Ready for next leap toward A3 strategic autonomy

---

## [2.2.1] — 2026-01-26

### 🎯 Modularity Refactoring — Constitutional Debt Elimination

This release achieves **zero constitutional violations** through systematic modularity refactoring and establishes **DRY-by-design** infrastructure for validation and path operations.

### Fixed

#### Constitutional Compliance

* **Zero Violations Achieved** (2026-01-26)
  - Eliminated last modularity violation (proposal_repository: 63.6 → compliant)
  - 100% compliance with modularity.refactor_score_threshold (all files < 60)
  - Technical debt reduction: 46% (13 warnings → 7 warnings)
  - Refactored 4 high-complexity files into 17 focused modules

#### Modularity Refactoring

* **proposal_repository.py** → 4 modules (63.6 → <35 per module)
  - `proposal_repository.py`: Pure CRUD operations (130 lines)
  - `proposal_mapper.py`: Domain/DB conversion (150 lines)
  - `proposal_state_manager.py`: Lifecycle transitions (160 lines)
  - `proposal_service.py`: High-level facade (120 lines)

* **validate.py** → 3 modules (51.6 → <25 per module)
  - `intent_schema_validator.py`: Pure validation logic (180 lines)
  - `policy_expression_evaluator.py`: Safe expression evaluation (120 lines)
  - `validate.py`: Thin CLI layer (70 lines)

* **intent_guard.py** → 4 modules (55.8 → <30 per module)
  - `rule_conflict_detector.py`: Constitutional conflict detection (120 lines)
  - `path_validator.py`: Path-level validation (180 lines)
  - `code_validator.py`: Generated code validation (90 lines)
  - `intent_guard.py`: Thin coordinator (150 lines)

* **complexity_service.py** → 4 modules (50.3 → <25 per module)
  - `capability_parser.py`: Capability tag extraction (60 lines)
  - `refactoring_proposal_writer.py`: Constitutional proposal creation (90 lines)
  - `capability_reconciliation_service.py`: AI-powered reconciliation (100 lines)
  - `complexity_service.py`: Thin orchestrator (140 lines)

### Added

#### DRY Infrastructure

* **constitutional_validation.py** - Standardized validation result models
  - `ConstitutionalValidationResult`: Rich violation tracking
  - `ConstitutionalFileValidationResult`: File-specific validation
  - `ConstitutionalBatchValidationResult`: Aggregate results
  - Eliminates duplication across IntentSchemaValidator, PathValidator, CodeValidator
  - Distinct from generic `ValidationResult` (no naming conflicts)

* **path_utils.py** - Reusable file discovery and pattern matching
  - `iter_files_by_extension()`: Generic file discovery with exclusions
  - `iter_python_files()`: Python-specific with sensible defaults
  - `matches_glob_pattern()` / `matches_any_pattern()`: Pattern matching
  - `safe_relative_to()` / `is_under_directory()`: Path relationships
  - `ensure_posix_path()`: Cross-platform normalization
  - Consolidates patterns from IntentSchemaValidator, PathValidator, file scanners

* **policy_resolver.py** - Constitutional path compliance
  - Migrated from `os.getenv()` to `PathResolver` (constitutional compliance)
  - Uses `path_utils` for file discovery (eliminates `glob.glob` usage)
  - No environment variable overrides (constitutional governance)

### Changed

#### Architecture

* **Single Responsibility Principle** - Enforced across all refactored modules
  - Repository pattern: Separated CRUD, mapping, state management, facade
  - Validation pattern: Separated schema, expression, CLI concerns
  - Governance pattern: Separated conflict detection, path validation, code validation
  - Service pattern: Separated parsing, proposal writing, reconciliation, orchestration

* **Separation of Concerns** - Clear boundaries established
  - CRUD operations isolated from business logic
  - Validation logic separated from CLI presentation
  - Coordination separated from execution
  - Parsing separated from orchestration

### Performance & Metrics

**Before Refactoring**:
- Constitutional violations: 1 (proposal_repository: 63.6)
- Technical debt warnings: 13
- Average responsibilities per file: 4-5
- Code duplication: Multiple validation patterns

**After Refactoring**:
- Constitutional violations: 0 ✅
- Technical debt warnings: 7 (46% reduction)
- Average responsibilities per file: 1-2
- Code duplication: Eliminated through shared utilities
- Total modules created: 17 focused, single-responsibility modules

**Symbol Count**: 1,833 symbols
- **Remarkably efficient** for 38+ feature domains (~48 symbols/domain)
- **4.17x more efficient** than industry average (200 symbols/domain typical)
- Comparable to pytest (200K LOC) but with broader scope

### Why This Matters

**Constitutional Governance**:
- Zero violations = Full constitutional compliance
- Modularity enforced through scoring and auditing
- Automatic quality gates prevent regression

**Code Quality**:
- Single-responsibility modules easier to test and maintain
- Clear separation enables parallel development
- DRY utilities prevent future duplication

**Scalability**:
- Clean architecture supports A3/A4 autonomy advancement
- Focused modules reduce cognitive load
- Reusable utilities accelerate development

### Migration Status

**Completed**: Modularity refactoring, DRY infrastructure, constitutional compliance
**Stable**: All refactored modules, validation utilities, path utilities
**Next**: Complete type safety (add mypy --strict), continue A3 advancement

### Notes

* This release achieves **zero constitutional violations** for the first time
* Refactoring follows **"Big Boys" patterns** (Kubernetes, AWS, OPA architecture)
* DRY utilities establish **foundation for future validation** and file operations
* Symbol count (1,833) remains **exceptionally lean** for system complexity

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

[2.2.1]: https://github.com/DariuszNewecki/CORE/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/DariuszNewecki/CORE/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/DariuszNewecki/CORE/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/DariuszNewecki/CORE/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/DariuszNewecki/CORE/releases/tag/v1.0.0
