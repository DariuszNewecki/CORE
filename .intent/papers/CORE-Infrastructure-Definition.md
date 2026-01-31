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
   * Services must be declared in database or hardcoded
   * No runtime decision about service availability
   * No conditional service loading based on context

2. **Validate Service Requests**
   * Cannot reject requests based on "appropriateness"
   * Cannot enforce access control
   * Can only fail if service doesn't exist (mechanical failure)

3. **Modify Service Behavior**
   * Cannot wrap services with additional logic
   * Cannot inject middleware based on conditions
   * Cannot alter initialization parameters strategically

4. **Track Service Usage for Decisions**
   * May log for telemetry
   * MUST NOT use logs to alter behavior
   * MUST NOT implement usage-based policies

### 5.3 ServiceRegistry Constitutional Obligations

**Transparency:**
```python
async def get_service(self, name: str) -> Any:
    """Get or create service with constitutional logging."""
    logger.info(
        "INFRASTRUCTURE: service_request",
        service=name,
        cached=name in self._instances,
        authority="infrastructure_coordination"
    )
    # ... instantiation logic ...
```

**Determinism:**
* Same service name → same service instance (or same instantiation logic)
* No hidden context switching
* No temporal dependencies

**Non-Interpretation:**
* Service names are opaque strings
* No semantic understanding of what services do
* No decisions based on service purpose

---

## 6. Infrastructure Exemption Mechanism

### 6.1 Constitutional Exemption

Infrastructure components are exempt from:
* Mind/Body/Will layer restrictions
* Import boundary enforcement (may import from any layer)
* Strategic decision prohibition (no decisions to make)

Infrastructure components remain subject to:
* Authority boundary enforcement (defined in this paper)
* Audit logging requirements
* Determinism requirements
* Constitutional visibility

### 6.2 Claiming Infrastructure Status

**A component MAY claim infrastructure status only if:**

1. It meets all four criteria in Section 3
2. It respects authority boundaries in Section 4
3. It is explicitly documented in this paper or amendments
4. It provides transparent audit logging

**A component MUST NOT claim infrastructure status if:**

1. It makes any strategic decision
2. It contains business logic
3. It evaluates constitutional rules
4. It interprets operations semantically

### 6.3 Infrastructure Registry

**Current Infrastructure Components:**

| Component | Location | Justification | Authority Limit |
|-----------|----------|---------------|-----------------|
| `ServiceRegistry` | `shared/infrastructure/service_registry.py` | Dependency injection coordinator | Cannot decide which services to provide |
| `SessionManager` | `shared/infrastructure/database/session_manager.py` | Database connection lifecycle | Cannot decide when to grant sessions |
| `ConfigService` | `shared/infrastructure/config_service.py` | Configuration key-value store | Cannot interpret configuration semantics |
| `QdrantService` | `shared/infrastructure/clients/qdrant_client.py` | Vector store client wrapper | Cannot decide what to vectorize |

**Adding to Infrastructure Registry:**

To declare a component as infrastructure, you must:
1. Add entry to table above
2. Document why it meets Section 3 criteria
3. Define its authority limits
4. Update enforcement mappings to exempt it

**This is a constitutional amendment process.**

---

## 7. Enforcement

### 7.1 Infrastructure Boundary Enforcement

**New Constitutional Rule:**
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

**Rationale:** Advisory enforcement allows drift. Infrastructure must be mechanically pure.

### 7.2 Infrastructure Audit Requirements

**All infrastructure components MUST:**

1. **Log State Transitions**
   ```python
   logger.info("INFRASTRUCTURE: event_type", **context)
   ```

2. **Expose Health Checks**
   ```python
   async def health_check(self) -> dict[str, Any]:
       """Report infrastructure health status."""
   ```

3. **Document Authority Claims**
   ```python
   """
   CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)
   AUTHORITY LIMITS: Cannot decide which services to instantiate
   EXEMPTIONS: May import from any layer for wiring
   """
   ```

### 7.3 Violation Detection

**Infrastructure violates this paper if:**

* It contains conditional logic based on domain semantics
* It implements retry logic with strategic backoff (vs mechanical retry)
* It logs errors and changes behavior based on error patterns
* It wraps operations with domain-specific validation

**Example Violations:**

```python
# VIOLATION: Strategic decision
async def get_service(self, name: str):
    if name in self.high_priority_services:
        return await self._fast_path(name)
    else:
        return await self._slow_path(name)
    # Infrastructure chose between strategies - NOT ALLOWED

# VIOLATION: Risk assessment
async def get_service(self, name: str):
    service = self._create_service(name)
    if self._seems_dangerous(service):
        raise SecurityException()
    # Infrastructure evaluated safety - NOT ALLOWED

# CORRECT: Mechanical coordination
async def get_service(self, name: str):
    if name not in self._service_map:
        raise ValueError(f"Service {name} not registered")
    return self._create_service(name)
    # Pure coordination, no judgment - ALLOWED
```

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
- [ ] Design BootstrapRegistry (ungovernanced) vs RuntimeRegistry (governanced)
- [ ] Create migration plan

### Phase 4: Constitutional Split (MONTH 2-3)
- [ ] Extract BootstrapRegistry for system initialization
- [ ] Move RuntimeRegistry to Body layer
- [ ] Subject RuntimeRegistry to full constitutional governance
- [ ] Update all callers to use appropriate registry

**Goal:** ServiceRegistry either IS pure infrastructure, or we split it until it is.

---

## 9. Why This Matters

### 9.1 Architectural Integrity

**Without Infrastructure Definition:**
* Components bypass governance by claiming "we're special"
* Constitutional coverage has holes
* Mind/Body/Will separation becomes aspirational
* Governance erodes through exception accumulation

**With Infrastructure Definition:**
* Every component has explicit constitutional status
* Exemptions are bounded and auditable
* Authority limits are clear and enforceable
* No component operates without oversight

### 9.2 Trust and Credibility

**Current State:**
> "CORE has constitutional governance... except for the parts we don't talk about"

**Target State:**
> "CORE has constitutional governance. Infrastructure is explicitly defined and bounded. Nothing operates without authority."

**For Academic/Research Validation:**
* Shows mature understanding of governance edge cases
* Demonstrates willingness to acknowledge and bound exceptions
* Provides template for other systems facing similar issues

**For Production Deployment:**
* Eliminates shadow government risk
* Makes infrastructure audit-able
* Provides clear upgrade path (Phase 4 split)

---

## 10. Relationship to Other Constitutional Documents

**This Paper Depends On:**
* `CORE-CONSTITUTION-v0.md` - Defines primitives (Document, Rule, Phase, Authority)
* `CORE-Mind-Body-Will-Separation.md` - Defines the three layers this exempts from
* `CORE-Constitutional-Foundations.md` - Establishes what "constitutional" means

**This Paper Extends:**
* Mind/Body/Will from 3 layers to "3 layers + bounded infrastructure"
* Authority model from 4 types to "4 types + infrastructure coordination"

**This Paper Enables:**
* `CORE-ServiceRegistry-Split.md` (future) - Plan to eliminate infrastructure exemption
* Infrastructure health monitoring and telemetry
* Clear upgrade path to fully governanced system

---

## 11. Constitutional Amendment Path

**This paper will eventually be obsoleted by:**

**Phase 4 Completion:**
* All infrastructure becomes either:
  * True bootstrap code (runs once, no governance needed), or
  * Governed Body components (subject to full constitutional rules)
* Infrastructure exemption shrinks to near-zero
* ServiceRegistry becomes either pure bootstrap or governed runtime component

**Target End State:**
* BootstrapRegistry: 50 lines, runs once at startup, ungovernanced
* RuntimeServiceRegistry: Full Body component, fully governanced
* Infrastructure exemption: Only bootstrap code, clearly separated

**Constitutional Evolution:**
```
v0.0: Mind/Body/Will (implicit infrastructure)
v0.1: Mind/Body/Will + Infrastructure (this paper)
v0.2: Mind/Body/Will + Bootstrap (infrastructure mostly eliminated)
v1.0: Pure Mind/Body/Will (infrastructure fully eliminated or governed)
```

---

## 12. Conclusion

Infrastructure is not a failure of constitutional governance.

Infrastructure is an acknowledgment that coordination machinery exists and must be bounded.

This paper:
* Defines what infrastructure is (and isn't)
* Establishes clear authority boundaries
* Acknowledges ServiceRegistry as infrastructure
* Provides path to eliminate infrastructure exemption over time

**ServiceRegistry is now constitutionally visible, bounded, and accountable.**

The governance blind spot is closed.

---

## Appendix A: Implementation Checklist

**Immediate (This Week):**
- [ ] Add this paper to `.intent/papers/CORE-Infrastructure-Definition.md`
- [ ] Reference from `.intent/CORE-CHARTER.md`
- [ ] Create `.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml`
- [ ] Update `src/shared/infrastructure/service_registry.py` docstring with constitutional authority claim
- [ ] Add audit logging to `ServiceRegistry.get_service()`
- [ ] Add audit logging to `ServiceRegistry.prime()`
- [ ] Add `ServiceRegistry.health_check()` method

**Near-Term (This Month):**
- [ ] Review all components in `src/shared/infrastructure/`
- [ ] Document each as infrastructure or reclassify
- [ ] Update Infrastructure Registry table (Section 6.3)
- [ ] Run constitutional audit with new infrastructure rules
- [ ] Address any infrastructure violations discovered

**Long-Term (This Quarter):**
- [ ] Design BootstrapRegistry / RuntimeRegistry split
- [ ] Create migration plan with backward compatibility
- [ ] Implement split in feature branch
- [ ] Validate split maintains constitutional compliance
- [ ] Deploy split as constitutional amendment

---

## Appendix B: Infrastructure Acid Test

**Question:** Is this component infrastructure?

**Test:**
```python
def is_infrastructure(component) -> bool:
    """Constitutional infrastructure test."""

    # Test 1: Can it choose between alternatives?
    if component.makes_strategic_decisions():
        return False  # NOT infrastructure

    # Test 2: Does it contain domain knowledge?
    if component.has_business_logic():
        return False  # NOT infrastructure

    # Test 3: Can it operate on arbitrary domains?
    if not component.is_domain_agnostic():
        return False  # NOT infrastructure

    # Test 4: Is its behavior deterministic?
    if not component.is_deterministic():
        return False  # NOT infrastructure

    return True  # IS infrastructure
```

**Apply to ServiceRegistry:**
* Makes strategic decisions? **NO** - Just wires things
* Contains business logic? **NO** - Pure coordination
* Domain agnostic? **YES** - Works with any services
* Deterministic? **YES** - Same inputs → same outputs

**Result: ServiceRegistry IS infrastructure ✓**

---

**END OF PAPER**

This paper closes the constitutional blind spot identified in the architectural review.

ServiceRegistry is now explicitly defined, bounded, and accountable.

All components now have constitutional status. No exceptions.

CORE's governance is complete.
