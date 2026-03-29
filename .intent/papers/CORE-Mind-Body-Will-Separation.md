# CORE: Mind/Body/Will Architectural Separation

**Status:** Constitutional Paper

**Authority:** Constitution-level (derivative, non-primitive)

**Depends on:**
* `constitution/CORE-CONSTITUTION-v0.md`
* `papers/CORE-Constitutional-Foundations.md`

---

## 1. Purpose

This paper defines the Mind/Body/Will architectural separation that structures all CORE implementation.

This separation is not organizational convenience. It is constitutional law.

Violations of this separation constitute governance failures, not merely poor design.

---

## 2. The Three Layers

CORE implementation is divided into exactly three architectural layers.

No component may exist outside these layers.

### 2.1 Mind — Law & Governance

**Location:** `.intent/` directory and `src/mind/`

**Responsibility:** Defines what is allowed, required, or forbidden.

**Characteristics:**
* Contains constitutional documents, rules, policies, schemas
* Defines governance but does not execute it
* Read-only to all runtime components
* Never performs I/O operations (DB, filesystem, network)
* Never makes decisions about which action to take
* Never executes actions

**Mind is law, not execution.**

---

### 2.2 Body — Pure Execution

**Location:** `src/body/`

**Responsibility:** Executes operations without making decisions about which operation to perform.

**Characteristics:**
* Implements atomic actions and services
* Receives explicit instructions (never chooses between options)
* May access infrastructure (database, filesystem, network)
* Returns results without interpretation
* Does not evaluate rules or policies
* Does not decide strategy or priorities

**Body is capability, not judgment.**

---

### 2.3 Will — Decision & Orchestration

**Location:** `src/will/`

**Responsibility:** Decides which actions to take, when, and in what order.

**Characteristics:**
* Orchestrates Body actions based on Mind rules
* Makes strategic decisions about goals and approaches
* Evaluates options and selects paths
* Does not implement actions directly (delegates to Body)
* Does not define law (reads from Mind)
* May access infrastructure only for decision-making context

**Will is judgment, not law or execution.**

---

## 3. Separation Rules

The following rules define enforceable boundaries between layers.

### Rule 3.1: Mind Never Executes

Components in Mind layer:
* MUST NOT perform database operations
* MUST NOT perform filesystem writes
* MUST NOT perform network operations
* MUST NOT invoke Body or Will components
* MAY read from `.intent/` directory
* MAY validate data structures
* MAY evaluate rules against provided evidence

**Rationale:** Law that executes itself becomes self-legitimizing.

---

### Rule 3.2: Body Never Decides

Components in Body layer:
* MUST NOT choose between alternative actions
* MUST NOT evaluate constitutional rules
* MUST NOT implement orchestration logic
* MUST receive explicit parameters for all operations
* MAY access all infrastructure as needed for execution
* MAY return structured results

**Rationale:** Execution without bounds becomes arbitrary power.

---

### Rule 3.3: Will Never Implements

Components in Will layer:
* MUST NOT implement atomic actions directly
* MUST NOT bypass Body to access infrastructure
* MUST delegate all execution to Body
* MAY read from Mind to understand constraints
* MAY decide which Body actions to invoke
* MAY access infrastructure only for decision context (not execution)

**Rationale:** Decision-making that implements itself cannot be governed.

---

## 4. Infrastructure Access Rules

Infrastructure (database, filesystem, network) access is governed by layer.

### 4.1 Database Access

**Allowed:**
* Body components MAY import and use `get_session` directly
* Shared infrastructure components MAY provide session management

**Forbidden:**
* Mind components MUST NOT access database
* Will components MUST NOT import `get_session` directly
* Will MAY receive database objects as read-only context
* API components MUST NOT import `get_session` directly

**Enforcement:** AST gate on `from shared.infrastructure.database.session_manager import get_session`

---

### 4.2 Filesystem Access

**Allowed:**
* Body components MAY read/write filesystem as needed
* Mind components MAY read `.intent/` directory only

**Forbidden:**
* Mind components MUST NOT write to filesystem
* Will components SHOULD delegate filesystem operations to Body

---

### 4.3 Network Access

**Allowed:**
* Body components MAY perform network operations
* Shared infrastructure MAY provide network clients

**Forbidden:**
* Mind components MUST NOT perform network operations
* Will components SHOULD delegate network operations to Body

---

## 5. Cross-Layer Communication

Layers communicate through explicit interfaces only.

### 5.1 Will → Mind

Will reads rules and policies from Mind to understand constraints.

This is **query**, not **execution**.

Will never modifies Mind.

---

### 5.2 Will → Body

Will invokes Body services with explicit parameters.

This is **delegation**, not **implementation**.

Will never implements what Body should do.

---

### 5.3 Body → Mind

Body MAY call Mind validators to check legality of proposed actions.

This is **verification**, not **decision-making**.

Body never decides whether to act based on Mind rules — that is Will's role.

---

### 5.4 Forbidden Paths

The following communication paths are **constitutionally prohibited**:

* Mind → Body (law executing itself)
* Mind → Will (law making decisions)
* Body → Will (execution choosing strategy)

---

## 6. API Layer Exception

The API layer (`src/api/`) is a special case:

* API is an **entrypoint boundary**, not an architectural layer
* API components MUST route all work through Will
* API components MUST NOT access infrastructure directly
* API components MUST NOT implement business logic

**Rationale:** API is a translation layer between external requests and internal architecture. It belongs to no layer and must not bypass the separation.

---

## 7. Shared Infrastructure — The Constitutional Fourth Primitive

### 7.1 What Shared Is

`src/shared/` is not a fourth architectural layer. It is **layer-independent infrastructure** — code that exists to serve all three layers without belonging to any of them.

The distinction is constitutional, not organizational. A layer has a role in the governance model: Mind governs, Body executes, Will decides. Shared has no role. It provides tools. It makes no decisions, defines no law, executes no strategy.

**Shared is the substrate the layers run on.**

---

### 7.2 The Admission Test

A module belongs in `src/shared/` if and only if it satisfies **all three** of the following:

**Test 1 — Layer Independence**
The module imports nothing from `src/mind/`, `src/body/`, or `src/will/`. If it imports from any layer, it belongs in a layer — either the one it imports from, or a higher one. There are no exceptions to this test.

**Test 2 — No Strategic Decisions**
The module does not decide which action to take, which goal to pursue, or which path to follow. It may compute, transform, validate, or communicate — but it does not choose. Choice belongs to Will.

**Test 3 — No Rule Evaluation**
The module does not evaluate constitutional rules against evidence. It may define data structures that rules operate on, but it does not determine compliance. Evaluation belongs to Mind.

If a module fails any test, it does not belong in `src/shared/`. The admission test is the enforcement gate. No exceptions, no "close enough."

---

### 7.3 Three Legitimate Categories

Modules that pass the admission test fall into one of three categories:

**Category 1 — Infrastructure Primitives**
Foundational machinery all layers consume: database session management, vector store clients, file handler, bootstrap registry, configuration, logging, AI client wrappers, knowledge service, intent repository. These are the plumbing of CORE. They have no opinion about what flows through them.

**Category 2 — Cross-Layer Protocols and Interfaces**
Abstract interfaces that allow layers to communicate without coupling. A Body service that Will needs to call should define its interface in `shared/protocols/` — Will depends on the protocol, Body implements it, neither depends on the other. This is the constitutional mechanism for eliminating circular imports between layers.

**Category 3 — Pure Utilities**
Deterministic algorithms and data structures with zero layer dependencies: parsers, normalizers, transformers, data models, utility functions. The defining characteristic is not what they do but what they do not import. If the module's entire dependency graph stays within `shared/` and the Python standard library, it belongs here.

---

### 7.4 What Is Forbidden in Shared

The following patterns are constitutional violations in `src/shared/`:

* Any import from `src/mind/`, `src/body/`, or `src/will/`
* Strategic decision-making (choosing between options based on goals)
* Rule evaluation (determining constitutional compliance)
* Worker base classes that encode daemon lifecycle — the Worker base class is permitted in `shared/workers/` only because it provides pure scaffolding with no layer-specific logic; the moment it encodes strategic behavior it must move to Will
* LLM invocation logic — `shared/ai/` may wrap the transport layer but must not encode prompt strategy or cognitive roles; those belong to Will

---

### 7.5 The Historical Failure Mode

The typical failure is: a module is ambiguous — it feels too "cognitive" for Body but has no Will infrastructure — so it gets placed in `shared/` by default. Over time, `shared/` accumulates modules that don't pass the admission test, and the constitutional grey zone grows.

The admission test exists precisely to prevent this. The question is never "where does this feel like it belongs?" The question is always "does it pass all three tests?" If yes — `shared/`. If no — determine which layer owns it and place it there.

Today's example: `remediation_interpretation/` is deterministic analysis logic with no layer imports. It passes all three tests. It belongs in `shared/`. The fact that it was previously in `will/` was a placement error, not a constitutional intent.

---

### 7.6 Enforcement

The rule `architecture.shared.no_strategic_decisions` is upgraded from advisory (`knowledge_gate`) to a blocking AST gate covering:

* Forbidden imports from any of the three layers
* Strategic decision patterns

This is declared in `.intent/enforcement/mappings/architecture/layer_separation.yaml` and applies to all of `src/shared/**/*.py`.

**Shared that drifts into layers is detectable and blockable. It must be.**

---

## 8. Enforcement Strategy

This separation is enforced at multiple phases:

### 8.1 Parse Phase
* Validate that files exist in correct directories
* Validate that layer structure is respected

### 8.2 Audit Phase
* Check for forbidden import patterns
* Verify cross-layer communication follows rules
* Detect strategic decision-making in Body
* Detect action implementation in Will
* Detect execution in Mind

### 8.3 Runtime Phase
* ServiceRegistry enforces dependency injection patterns
* Infrastructure access is monitored and logged

---

## 9. Why This Matters

Without Mind/Body/Will separation:

* Law becomes self-executing (ungovernable)
* Execution becomes unconstrained (dangerous)
* Decision-making becomes arbitrary (unpredictable)
* Testing becomes impossible (no boundaries to mock)
* Autonomy becomes uncontrollable (no separation of concerns)

With Mind/Body/Will separation:

* Law is stable and external to execution
* Execution is predictable and testable
* Decision-making is transparent and auditable
* Components can be replaced independently
* Autonomy operates within clear boundaries

---

## 10. Historical Note

This separation was CORE's founding architectural principle.

Its gradual dilution during development demonstrates why constitutional law must be explicit, enforced, and non-negotiable.

This paper restores what was always intended.

---

## 11. Implementation Requirement

All existing code violating this separation MUST be refactored.

No new code violating this separation MAY be merged.

This is not a suggestion. This is constitutional law.

---

## 12. Relationship to Other Papers

This paper assumes:
* `CORE-Constitutional-Foundations.md` (primitives and phases)
* `CORE-Deliberate-Non-Goals.md` (what CORE refuses to do)
* `CORE-Constitution-Read-Only-Contract.md` (Mind immutability)

It is referenced by enforcement mappings in:
* `.intent/enforcement/mappings/architecture/layer_separation.yaml`

---

## 13. Conclusion

Mind/Body/Will is not a metaphor.

It is the constitutional structure that makes CORE governable.

Without it, CORE becomes just another system claiming to have "good architecture."

With it, CORE is a system whose architecture is law.
