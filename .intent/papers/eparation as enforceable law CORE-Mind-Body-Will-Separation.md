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

## 7. Shared Infrastructure Exception

The Shared layer (`src/shared/`) provides infrastructure primitives:

* Shared components MAY access any infrastructure
* Shared components are **utilities**, not layers
* Shared components MUST NOT make strategic decisions
* Shared components MUST NOT evaluate constitutional rules

**Rationale:** Shared provides the tools that layers use. It is not itself a layer in the Mind/Body/Will model.

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
* `.intent/enforcement/mappings/architecture/mind_body_will_separation.yaml`

---

## 13. Conclusion

Mind/Body/Will is not a metaphor.

It is the constitutional structure that makes CORE governable.

Without it, CORE becomes just another system claiming to have "good architecture."

With it, CORE is a system whose architecture is law.
