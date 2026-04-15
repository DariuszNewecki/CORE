<!-- path: .intent/papers/CORE-Infrastructure-Definition.md -->

# CORE: Infrastructure Definition and Authority Boundaries

**Status:** Constitutional Paper (Foundational)

**Authority:** Constitution-level (derivative from primitives)

**Depends on:**
* `constitution/CORE-CONSTITUTION-v0.md`
* `papers/CORE-Mind-Body-Will-Separation.md`
* `papers/CORE-Constitutional-Foundations.md`

---

## 1. Purpose

This paper formally defines "Infrastructure" as a constitutional category and establishes its authority boundaries.

Infrastructure exists. It must be acknowledged and bounded, not ignored.

Without explicit definition, "infrastructure" becomes an expanding exemption space that undermines constitutional governance.

---

## 2. The Infrastructure Problem

**Observed Reality:**
* Some components provide mechanical coordination without strategic decisions
* These components must access multiple layers to perform their function
* Existing constitutional model (Mind/Body/Will) does not account for them
* They accumulate authority by default through omission

**Without This Paper:**
* "Infrastructure" remains undefined and ungovernanced
* Components can claim infrastructure status to bypass rules
* Constitutional blind spots accumulate
* Governance erodes through exception expansion

**With This Paper:**
* Infrastructure is explicitly defined and bounded
* Authority limits are clear and enforceable
* No component can claim infrastructure status without meeting criteria
* Constitutional coverage remains complete

---

## 3. Infrastructure Definition

**Infrastructure** is a constitutional category for components that:

1. **Provide Mechanical Coordination**
   * Connect components without deciding which components to use
   * Route requests without interpreting requests
   * Manage resources without allocating resources strategically

2. **Make Zero Strategic Decisions**
   * Contain no business logic
   * Perform no risk assessment
   * Exercise no judgment between alternatives
   * Execute deterministic algorithms only

3. **Remain Stateless Regarding Domain**
   * May maintain coordination state (connection pools, caches)
   * MUST NOT maintain business state
   * MUST NOT make decisions based on accumulated knowledge

4. **Have No Opinion on Correctness**
   * Cannot determine if operations are "good" or "bad"
   * Cannot block based on semantic understanding
   * Can only enforce mechanical constraints (types, formats)

**Infrastructure is machinery, not mind or will.**

---

## 3a. External System Wrappers — Bounded Domain Awareness

Some infrastructure components wrap external systems (vector stores, AI
clients, configuration databases). These components necessarily encode
knowledge of the external system's schema, API, and data format. This
is not a violation of criterion 4.

The distinction is:

**Permitted (structural awareness):** A component that knows the shape
of an external system's API — field names, collection names, endpoint
paths, data types — so it can translate CORE's requests into that
system's protocol. This is mechanical adaptation.

**Forbidden (correctness opinion):** A component that decides whether a
CORE operation is semantically correct, appropriate, or safe based on
domain knowledge. This is judgment.

Examples:
- `QdrantService` knowing the collection name and vector dimension is
  structural awareness — permitted.
- `QdrantService` deciding whether a symbol is "worth vectorizing" based
  on its content would be a correctness opinion — forbidden.
- `ConfigService` knowing that configuration values are stored by key
  is structural awareness — permitted.
- `ConfigService` deciding whether a configuration value represents a
  safe threshold would be a correctness opinion — forbidden.

Infrastructure wrappers for external systems pass the admission test
when their domain knowledge is limited to the external system's
structural schema, not to CORE's domain semantics.

---

## 4. Infrastructure Authority Boundaries

### 4.1 What Infrastructure MAY Do

**Permitted Operations:**
* **Dependency Injection** - Create and wire components
* **Session Management** - Create database connections, manage lifecycle
* **Resource Pooling** - Connection pools, thread pools, caches
* **Configuration Loading** - Read settings from database/environment
* **Logging and Telemetry** - Record what happened (not why)
* **Format Conversion** - Transform data shapes deterministically
* **Error Propagation** - Pass errors up, never suppress
* **External System Adaptation** - Translate requests to external system protocols

**Key Principle:** Infrastructure can facilitate but never adjudicate.

### 4.2 What Infrastructure MUST NOT Do

**Forbidden Operations:**
* **Strategic Decisions** - Choose between alternatives based on context
* **Risk Assessment** - Determine if operations are safe/allowed
* **Business Logic** - Implement domain rules or policies
* **Constitutional Enforcement** - Evaluate or apply governance rules
* **Interpretation** - Assign meaning to operations
* **Learning** - Adjust behavior based on history
* **Authorization** - Grant or deny access based on rules

**Key Principle:** If it requires judgment, it's not infrastructure.

---

## 5. ServiceRegistry: Infrastructure Classification

### 5.1 Constitutional Status

**ServiceRegistry is Infrastructure.**

**Justification:**
* Performs dependency injection (mechanical coordination)
* No strategic decisions about which services to provide
* Stateless regarding domain (maintains only coordination state)
* Does not interpret service requests
* Does not evaluate business rules

**Therefore:** ServiceRegistry is exempt from Mind/Body/Will layer restrictions.

### 5.2 ServiceRegistry Authority Limits

**What ServiceRegistry IS Authorized To Do:**

1. **Prime Database Session Factory**
   ```python
   @classmethod
   def prime(cls, session_factory: Callable) -> None:
       """Store the session factory for later use."""
   ```
   * Authority: Infrastructure coordination
   * Justification: Mechanical wiring, no decisions

2. **Provide Database Sessions**
   ```python
   @classmethod
   def session(cls):
       """Return a database session from the factory."""
   ```
   * Authority: Infrastructure coordination
   * Justification: Passes through factory, no interpretation

3. **Lazy-Load Services**
   ```python
   async def get_service(self, name: str) -> Any:
       """Instantiate service if not cached, return instance."""
   ```
   * Authority: Infrastructure coordination
   * Justification: Mechanical instantiation from registry

4. **Cache Service Instances**
   * Authority: Infrastructure optimization
   * Justification: Performance, not business logic

**What ServiceRegistry IS NOT Authorized To Do:**

1. **Decide Which Services to Provide**
2. **Validate Service Requests**
3. **Modify Service Behavior**
4. **Track Service Usage for Decisions**

### 5.3 ServiceRegistry Constitutional Obligations

**Transparency:**
```python
async def get_service(self, name: str) -> Any:
    logger.info(
        "INFRASTRUCTURE: service_request",
        service=name,
        cached=name in self._instances,
        authority="infrastructure_coordination"
    )
```

**Determinism:** Same service name → same service instance.

**Non-Interpretation:** Service names are opaque strings.

---

## 6. Infrastructure Exemption Mechanism

### 6.1 Constitutional Exemption

Infrastructure components are exempt from:
* Mind/Body/Will layer restrictions
* Import boundary enforcement (may import from any layer for wiring)
* Strategic decision prohibition (no decisions to make)

Infrastructure components remain subject to:
* Authority boundary enforcement (defined in this paper)
* Audit logging requirements
* Determinism requirements
* Constitutional visibility

### 6.2 Claiming Infrastructure Status

**A component MAY claim infrastructure status only if:**

1. It meets all four criteria in Section 3 (including the clarification in 3a for external system wrappers)
2. It respects authority boundaries in Section 4
3. It is explicitly documented in this paper or amendments
4. It provides transparent audit logging

**A component MUST NOT claim infrastructure status if:**

1. It makes any strategic decision
2. It contains business logic
3. It evaluates constitutional rules
4. It interprets operations semantically beyond external system adaptation

### 6.3 Infrastructure Registry

**Current Infrastructure Components:**

| Component | Location | Justification | Authority Limit |
|-----------|----------|---------------|-----------------|
| `ServiceRegistry` | `shared/infrastructure/service_registry.py` | Dependency injection coordinator | Cannot decide which services to provide |
| `SessionManager` | `shared/infrastructure/database/session_manager.py` | Database connection lifecycle | Cannot decide when to grant sessions |
| `ConfigService` | `shared/infrastructure/config_service.py` | Configuration key-value store | Cannot interpret configuration semantics; reads values by key only |
| `QdrantService` | `shared/infrastructure/clients/qdrant_client.py` | Vector store client wrapper | Encodes external system schema only; cannot decide what to vectorize |

**Note on QdrantService and ConfigService:** Both components encode
structural knowledge of their external systems (collection names,
vector dimensions, configuration key formats). This is permitted
external-system adaptation per section 3a. Neither component decides
whether a CORE operation is semantically correct or safe. That judgment
belongs to Body-layer services that call them.

**Adding to Infrastructure Registry:**

To declare a component as infrastructure, you must:
1. Add entry to table above
2. Document why it meets Section 3 criteria (citing 3a if applicable)
3. Define its authority limits explicitly
4. Update enforcement mappings to exempt it

This is a constitutional amendment process.

---

## 7. Enforcement

### 7.1 Infrastructure Boundary Enforcement

```yaml
# .intent/enforcement/mappings/infrastructure/authority_boundaries.yaml

infrastructure.no_strategic_decisions:
  engine: knowledge_gate
  params:
    check_type: component_responsibility
    expected_pattern: "Infrastructure provides coordination without strategic decisions"
  scope:
    applies_to:
      - "src/shared/infrastructure/**/*.py"
  enforcement: blocking
  authority: constitution
  phase: audit
```

### 7.2 Infrastructure Audit Requirements

All infrastructure components MUST:

1. Log state transitions with `INFRASTRUCTURE: event_type` prefix
2. Expose health checks via `health_check()` method
3. Document authority claims in class docstring

### 7.3 Violation Detection

Infrastructure violates this paper if it:
* Contains conditional logic based on domain semantics
* Implements retry logic with strategic backoff
* Logs errors and changes behavior based on error patterns
* Wraps operations with domain-specific validation

---

## 8. ServiceRegistry Hardening Roadmap

### Phase 1: Constitutional Documentation (IMMEDIATE)
- [x] Define infrastructure in constitutional terms
- [x] Document ServiceRegistry as infrastructure
- [x] Establish authority boundaries
- [ ] Add audit logging to all ServiceRegistry operations

### Phase 2: Enforcement Integration (WEEK 1)
- [ ] Add infrastructure exemption to layer_separation.yaml
- [ ] Create infrastructure/authority_boundaries.yaml enforcement mapping
- [ ] Update ServiceRegistry docstrings with constitutional claims
- [ ] Add health_check() method to ServiceRegistry

### Phase 3: Split Preparation (MONTH 1-2)
- [ ] Identify which ServiceRegistry methods are pure infrastructure
- [ ] Identify which methods contain decisions (move to Body)
- [ ] Design BootstrapRegistry vs RuntimeRegistry split

### Phase 4: Constitutional Split (MONTH 2-3)
- [ ] Extract BootstrapRegistry for system initialization
- [ ] Move RuntimeRegistry to Body layer
- [ ] Subject RuntimeRegistry to full constitutional governance

---

## 9. Relationship to Other Constitutional Documents

**This Paper Depends On:**
* `CORE-CONSTITUTION-v0.md`
* `CORE-Mind-Body-Will-Separation.md`
* `CORE-Constitutional-Foundations.md`

**This Paper Extends:**
* Mind/Body/Will from 3 layers to "3 layers + bounded infrastructure"

**This Paper Enables:**
* Infrastructure health monitoring and telemetry
* Clear upgrade path to fully governanced system

---

## 10. Constitutional Amendment Path

This paper will eventually be obsoleted when all infrastructure becomes
either true bootstrap code (runs once, ungovernanced) or governed Body
components. The infrastructure exemption shrinks to near-zero at that
point.

---

## 11. Conclusion

Infrastructure is not a failure of constitutional governance.

Infrastructure is an acknowledgment that coordination machinery exists
and must be bounded.

This paper defines what infrastructure is, establishes clear authority
boundaries, acknowledges the bounded domain awareness permitted for
external system wrappers, and provides a path to eliminate the
infrastructure exemption over time.

The governance blind spot is closed.

---

**END OF PAPER**
