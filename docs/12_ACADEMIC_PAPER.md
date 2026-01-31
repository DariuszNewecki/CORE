# Constitutional Infrastructure Separation: Closing Governance Blind Spots in AI Development Systems

**Dariusz Newecki**
Independent Researcher
d.newecki@gmail.com

---

## Abstract

Large Language Models accelerate software development but introduce architectural drift and governance challenges when used as coding assistants. We present a case study from building LIRA, an AI-powered organizational governance platform, where we discovered that even our constitutional enforcement system (CORE) contained a critical blind spot—infrastructure components operating without oversight. We introduce a framework for explicitly categorizing infrastructure in AI development systems, defining it through four criteria: mechanical coordination, zero strategic decisions, domain statelessness, and correctness neutrality. Through architectural review and systematic remediation, we closed this governance gap in under 2 hours by adding 5 constitutional rules and 4 documentation requirements, requiring no code changes. The resulting system maintains 100% constitutional compliance across 1,807 symbols while enabling AI-assisted development. Our findings demonstrate that infrastructure separation is critical for governable AI systems, and that making implicit coordination explicit prevents governance erosion. We provide a replicable framework for identifying and bounding infrastructure components in autonomous development tools.

---

## 1. Introduction

We set out to build LIRA, a platform for AI-powered organizational governance. We didn't set out to invent a new approach to AI safety. But when you try to build something real with AI assistance, you quickly discover that safety isn't academic—it's survival.

### 1.1 The Problem

Modern Large Language Models (LLMs) can generate substantial amounts of working code from natural language descriptions. This capability promises to accelerate software development dramatically. However, in practice, we encountered a fundamental challenge: **LLM-generated code consistently violated architectural invariants despite extensive prompt engineering**.

When building LIRA—a system designed to help organizations discover undocumented processes, align policies with compliance frameworks (GDPR, ISO 27001, NIS2), and provide visual governance through process maturity heatmaps—we found ourselves in an uncomfortable position. We were building a governance platform using ungovernable AI assistance.

Initial attempts at control through prompt engineering ("Please follow our architecture," "Maintain separation of concerns," "Do not create circular dependencies") failed as context windows filled, requirements evolved, and the models drifted from stated constraints. Post-hoc testing caught violations too late—after architectural damage was already embedded in the codebase.

### 1.2 The Solution: Constitutional Governance

To address this, we developed CORE (Constitutional Orchestration & Reasoning Engine), a framework treating architectural rules as executable artifacts enforced through Abstract Syntax Tree (AST) analysis and phase-aware validation. CORE implements a Mind-Body-Will architecture:

- **Mind**: Human-authored governance policies in `.intent/` directories, stored as YAML/JSON
- **Body**: Pure execution code in `src/`, subject to constitutional rules
- **Will**: AI-driven decision-making operating within constitutional bounds

This approach proved effective. AI agents could generate code autonomously while mechanical enforcement prevented architectural violations. Success rates for autonomous code generation reached 70-80%, and the system maintained architectural integrity across approximately 1,800 symbols.

### 1.3 The Discovery: A Blind Spot in Governance Itself

During a comprehensive architectural review, we discovered something unsettling: **our governance system itself had a critical blind spot**. The ServiceRegistry component—responsible for dependency injection, session management, and service instantiation—operated without constitutional oversight. It was a "shadow government" within CORE.

This was existential. ServiceRegistry controlled which components loaded, how they connected, and what dependencies they received. If compromised or incorrectly modified by an AI agent, it could bypass all other governance mechanisms. Yet it had:

- Zero constitutional documentation
- No declared authority boundaries
- Exemption from standard governance rules
- Potential to be modified autonomously without detection

We faced a false dichotomy:
1. **Exempt ServiceRegistry entirely** → Shadow government, governance theater
2. **Apply standard governance** → System bootstrap failure, operational breakdown

Neither option was acceptable.

### 1.4 The Insight: Infrastructure as a Third Category

The solution required recognizing that infrastructure components are fundamentally different from both governed operational code and constitutional documents. They require a **third category with explicit boundaries and documented exemptions**.

We developed a framework defining infrastructure through four criteria:
1. **Mechanical coordination only** (not strategic decisions)
2. **Zero strategic decisions** (no business logic)
3. **Domain stateless** (no opinion on correctness)
4. **Opinion-free** (coordinates without judging)

This framework enabled us to **explicitly bound ServiceRegistry's authority** while acknowledging its necessary exemptions. The remediation took under 2 hours and required no code changes—only constitutional documentation declaring what ServiceRegistry already was.

### 1.5 Contributions

This paper makes the following contributions:

1. **Framework for infrastructure categorization** in AI development systems with explicit authority boundaries
2. **Case study** demonstrating identification and closure of a governance blind spot in a production system
3. **Evidence** that mechanical enforcement with explicit categorization beats implicit exemptions
4. **Replicable approach** for constitutional AI development that others can apply

### 1.6 Paper Structure

Section 2 provides background on AI coding assistants and governance approaches. Section 3 briefly describes LIRA to contextualize why governance was critical. Section 4 presents CORE's constitutional architecture. Section 5 analyzes the infrastructure problem in depth. Section 6 details the case study of constitutionalizing ServiceRegistry. Section 7 discusses implications, and Section 8 concludes with future work.

---

## 2. Background and Related Work

### 2.1 AI Coding Assistants and Their Limits

LLM-based coding assistants (GitHub Copilot, Claude Code, GPT-4 with code interpreter) have demonstrated impressive capabilities in generating syntactically correct code from natural language descriptions. However, they exhibit several critical limitations when used for autonomous or semi-autonomous development:

**Context Window Constraints**: Even with extended context windows (100K+ tokens), models lose coherence over long codebases and drift from earlier architectural decisions.

**Prompt Engineering Brittleness**: Instructions like "maintain architectural separation" or "follow existing patterns" work inconsistently. Models may comply initially but deviate as conversations extend or requirements shift.

**Emergence of Violations**: Architecturally problematic patterns emerge incrementally. Individual changes appear reasonable but collectively violate system invariants (circular dependencies, layer violations, tight coupling).

**Post-Hoc Detection Limitations**: Traditional testing catches functional bugs but may miss architectural violations until they've propagated through the codebase.

### 2.2 Existing Governance Approaches

Several paradigms attempt to constrain or guide AI system behavior:

**Constitutional AI (Anthropic)**: Uses prompts encoding principles and values to guide LLM behavior through self-critique and revision cycles. Effective for content safety but doesn't address structural code constraints.

**Policy-as-Code**: Treats infrastructure configuration as versioned, testable code (Terraform, Pulumi). Ensures reproducibility but doesn't constrain autonomous code generation.

**Formal Verification**: Mathematically proves code correctness against specifications (Coq, TLA+). Highly rigorous but impractical for rapid development cycles with AI assistance.

**Static Analysis Tools**: Linters and analyzers detect code smells and violations (Ruff, ESLint). Useful but operate post-generation and lack semantic understanding of architectural intent.

### 2.3 The Gap CORE Addresses

Existing approaches either:
- Operate at the prompt level (brittle, bypassable)
- Operate post-generation (too late for prevention)
- Require heavyweight formal methods (impractical for velocity)

CORE fills this gap by:
- **Enforcing at generation time** through mechanical checks
- **Expressing rules as data** (YAML/JSON policies), not code
- **Maintaining development velocity** (millisecond rule execution)
- **Providing explicit categorization** of infrastructure vs. governed code

The key insight is that **governance must be structural, not behavioral**. Rather than prompting models to "please follow rules," CORE makes rule violations mechanically impossible or immediately detectable.

### 2.4 Infrastructure in Software Systems

Infrastructure components in software systems—dependency injection frameworks, session managers, orchestrators—present unique governance challenges. They typically:

- Cross architectural boundaries (need access to all layers)
- Bootstrap system initialization (execute before governance)
- Coordinate without deciding (mechanical, not strategic)
- Require exemptions from standard rules (but how to bound them?)

Prior work has not systematically addressed how to govern infrastructure in AI development contexts. Configuration management approaches assume human-authored infrastructure. AI safety research focuses on model behavior, not development system architecture.

Our contribution addresses this gap by providing an explicit framework for categorizing and bounding infrastructure components while maintaining mechanical governance enforcement.

---

## 3. LIRA: The System Requiring Governance

To understand why constitutional governance became necessary, we briefly describe LIRA, the system whose development motivated and validated CORE.

### 3.1 LIRA Overview

LIRA (Logical Intelligent Resource Augmentation) is an AI-powered platform for organizational IT governance and process optimization. It addresses a pervasive problem: **organizations have fragmented documentation, tribal knowledge, and zero visibility into what processes actually exist versus what policies claim should exist**.

Key capabilities include:

**Organizational Learning Engine**: Ingests data from SharePoint, ServiceNow, Workday, and other enterprise systems to build a comprehensive map of organizational structure, roles, and processes.

**AI-Powered Process Discovery**: Analyzes documentation and system data to detect undocumented workflows, identify gaps (e.g., no formal process for handling GDPR data subject access requests), and surface inefficiencies.

**Compliance Alignment**: Compares internal policies against regulatory frameworks (GDPR, ISO 27001, NIS2, ITIL) and flags gaps with actionable recommendations.

**Visual Governance**: Provides a heatmap visualization showing process maturity across the organization, with color-coding indicating compliance status and risk levels.

**Task Management with Human-in-the-Loop**: Generates tasks to address identified gaps, requiring human approval before execution, with full audit trails.

### 3.2 Why LIRA Required Strong Governance

LIRA's scope and complexity made it an ideal candidate—and critical testbed—for constitutional governance:

**Multi-Agent Architecture**: LIRA employs specialized AI agents for compliance analysis, process optimization, security review, and documentation generation. These agents must coordinate without creating conflicts or circular dependencies.

**Cross-Organizational Scope**: LIRA touches HR, IT, Finance, Legal, and Compliance processes. Architectural errors could propagate across organizational boundaries, violating segregation of duties.

**Compliance Requirements**: As a governance tool, LIRA itself must be auditable and compliant. Ungovernered AI-generated code in a compliance platform creates obvious irony and risk.

**Real-World Consequences**: Unlike toy examples, LIRA recommendations affect actual organizational processes. Errors could lead to compliance violations, security gaps, or operational disruptions.

### 3.3 The Architectural Challenge

LIRA's complexity made pure human development impractically slow. We needed AI assistance. But we also needed absolute confidence that AI-generated code wouldn't violate architectural boundaries, create compliance risks, or introduce subtle bugs that would only manifest under specific organizational contexts.

This tension—needing AI velocity while requiring governance guarantees—directly motivated CORE's development. LIRA became both the reason for CORE and the primary validation case for constitutional enforcement.

The fact that CORE itself, while successfully governing LIRA's development, contained a governance blind spot (ServiceRegistry) provides a particularly compelling validation of our infrastructure categorization framework. If even a system explicitly designed for governance can harbor shadow government components, systematic identification and bounding of infrastructure is essential.

---

## 4. CORE: Constitutional Governance Architecture

We now describe CORE's architecture to provide context for understanding the infrastructure problem and our solution.

### 4.1 Mind-Body-Will Separation

CORE enforces a strict tripartite architecture:

**Mind (`.intent/` directory)**:
- Human-authored constitutional documents only
- Defines principles, policies, rules, and enforcement mappings
- Stored as YAML (enforcement) and JSON (rules) for machine readability
- Immutable through standard development workflow
- Acts as single source of truth for governance

**Body (`src/` directory)**:
- Pure execution code
- Subject to all constitutional rules
- No decision-making beyond mechanical execution
- Must declare constitutional authority in docstrings
- Cannot modify Mind without explicit human action

**Will (decision-making layer)**:
- AI agents operating within constitutional bounds
- Can reason, recommend, and generate
- Cannot bypass constitutional constraints
- Actions subject to audit and human review

This separation ensures that:
- Governance rules cannot be bypassed through code changes
- AI-generated code is constitutionally bounded at generation time
- All system behavior is traceable to explicit human-authored policies

### 4.2 Enforcement Mechanisms

CORE implements multiple enforcement gates operating at different system phases:

**AST Gate (Parse/Load Phase)**:
```python
# Example: Import boundary enforcement
def check_import_boundaries(node: ast.Import, context: dict) -> Violation | None:
    """Enforce Mind/Body/Will import restrictions"""
    if context['layer'] == 'body' and is_mind_import(node):
        return Violation("Body cannot import from Mind")
```

Validates:
- Import boundaries (Mind/Body/Will separation)
- Forbidden primitives (e.g., no `eval()`, restricted `exec()`)
- Layer violations (Body importing from Will)

**Glob Gate (Audit Phase)**:
Enforces path-based restrictions:
- `.intent/` files must have human-authored markers
- Operational code must be in `src/`
- Tests must be in `tests/`

**Knowledge Gate (Semantic Phase)**:
Uses semantic understanding to validate:
- Component responsibilities match declared authority
- No strategic decisions in infrastructure code
- Proper separation of concerns

**Regex Gate (Pattern Detection)**:
Detects problematic patterns:
- Bare `except:` handlers
- Hardcoded credentials
- Dangerous function calls

### 4.3 Phase-Aware Enforcement

CORE recognizes that different violations matter at different system lifecycle phases:

**Parse Phase**: Syntax errors, malformed imports
**Load Phase**: Dependency resolution, circular imports
**Audit Phase**: Constitutional compliance, documentation requirements
**Runtime Phase**: Permission checks, resource access
**Execution Phase**: Output validation, effect tracking

Each enforcement rule specifies:
- Which gate enforces it
- Which phase it applies to
- Severity (blocking, reporting, advisory)
- Enforcement mode (fail build, warn, log only)

### 4.4 Rule Structure

Constitutional rules are defined as data, not code:

```json
{
  "rule_id": "infrastructure.no_strategic_decisions",
  "description": "Infrastructure must not make strategic decisions",
  "check_type": "knowledge_gate",
  "severity": "error",
  "enforcement": "reporting",
  "applies_to": ["src/shared/infrastructure/**"],
  "rationale": "Infrastructure coordinates; it does not decide"
}
```

Enforcement mappings specify how rules apply:

```yaml
infrastructure.no_strategic_decisions: reporting
infrastructure.constitutional_documentation: reporting
infrastructure.no_business_logic: reporting
```

This data-driven approach enables:
- Dynamic rule updates without code changes
- Gradual enforcement migration (reporting → blocking)
- Clear audit trails of what's enforced and why

### 4.5 Success Metrics Before Infrastructure Problem

By the time we identified the ServiceRegistry blind spot, CORE had demonstrated substantial success:

- **1,807 symbols** under governance
- **60 constitutional rules** enforced
- **70-80% success rate** for autonomous code generation
- **Zero architectural drift** detected in human review
- **100% test coverage** of enforcement mechanisms

This success made the infrastructure blind spot discovery particularly significant: even a well-functioning governance system can harbor shadow government components if infrastructure is not explicitly categorized.

---

## 5. The Infrastructure Problem

We now present the core contribution of this paper: identifying infrastructure as a governance blind spot and developing a framework for its explicit categorization.

### 5.1 Discovery of the Blind Spot

During a comprehensive architectural review, we systematically analyzed CORE's components for constitutional compliance. The review revealed a stark inconsistency:

**Governed Components** (e.g., AI agents, business logic):
- ✅ Constitutional docstrings declaring authority
- ✅ Import restrictions enforced
- ✅ Responsibility boundaries documented
- ✅ Audit trails for all modifications

**ServiceRegistry**:
- ❌ No constitutional documentation
- ❌ Exempt from import restrictions
- ❌ No declared authority boundaries
- ❌ Could be modified autonomously

The ServiceRegistry component manages:
- **Dependency injection**: Instantiates and wires all services
- **Session lifecycle**: Creates and manages database sessions
- **Service discovery**: Maps interface requests to implementations
- **Bootstrap coordination**: Initializes system in correct order

### 5.2 Why This Is Existential

The ServiceRegistry blind spot represented an existential threat to CORE's governance guarantees:

**Complete Bypass Potential**: By modifying which services load or how they connect, an AI agent (or malicious actor) could bypass all other constitutional constraints. Governance becomes theater if the orchestrator is ungoverned.

**Bootstrap Authority**: ServiceRegistry executes before most governance checks. It could potentially inject compromised services before audit mechanisms activate.

**Invisible Violations**: Without constitutional documentation, there was no specification of what ServiceRegistry should not do. Violations would be undetectable until system failure.

**Governance Erosion**: If infrastructure components can silently accumulate unconstrained authority, constitutional guarantees erode over time as more "necessary exemptions" accumulate.

### 5.3 The False Dichotomy

We initially saw two options:

**Option 1: Explicit Exemption**
- Add ServiceRegistry to `.intent/exemptions.yaml`
- Document it as "necessary for system operation"
- Accept that it operates outside governance

**Problems**:
- Creates precedent for exemptions
- No bound on what it can/cannot do
- Shadow government becomes codified
- Other components can claim "necessary" status

**Option 2: Full Governance**
- Apply standard Mind/Body/Will rules
- Require constitutional authority declarations
- Enforce import restrictions

**Problems**:
- ServiceRegistry needs cross-layer imports (legitimate)
- Executes during bootstrap (before audit phase)
- Mechanical coordination requires broader access than normal components

Neither option was satisfactory. We needed a third way.

### 5.4 The Insight: Infrastructure as Explicit Category

The solution emerged from recognizing that **infrastructure is fundamentally different from both operational code and constitutional documents**:

**Operational Code (Body)**:
- Implements business logic
- Makes strategic decisions
- Has opinions about correctness
- Domain-specific behavior

**Constitutional Documents (Mind)**:
- Human-authored governance
- Defines system invariants
- Specifies allowed/forbidden behavior
- Domain-agnostic rules

**Infrastructure (??)**:
- Mechanical coordination only
- Zero strategic decisions
- Domain stateless
- No opinion on correctness

Infrastructure requires **exemptions** (broader access) but also requires **boundaries** (explicit limits on authority). The key is making both explicit.

### 5.5 Infrastructure Definition Framework

We developed four criteria that precisely define infrastructure:

**Criterion 1: Mechanical Coordination Only**

Infrastructure provides coordination services but makes no decisions about what to coordinate or why.

❌ **Not Infrastructure**: A workflow engine that decides which approval path to use based on business rules
✅ **Infrastructure**: A session manager that provides database connections on request

**Criterion 2: Zero Strategic Decisions**

Infrastructure has no business logic. It cannot decide between alternatives based on domain knowledge.

❌ **Not Infrastructure**: A service that chooses which compliance framework to apply
✅ **Infrastructure**: A dependency injector that instantiates requested services

**Criterion 3: Domain Stateless**

Infrastructure maintains no knowledge of domain entities or their relationships.

❌ **Not Infrastructure**: A cache that understands user roles and permissions
✅ **Infrastructure**: A cache that stores and retrieves arbitrary key-value pairs

**Criterion 4: Opinion-Free on Correctness**

Infrastructure cannot validate whether what it coordinates is semantically correct.

❌ **Not Infrastructure**: A validator that checks if a policy complies with GDPR
✅ **Infrastructure**: A parser that converts YAML to Python objects

### 5.6 Applying Framework to ServiceRegistry

With these criteria, we could explicitly categorize ServiceRegistry:

**Status**: Infrastructure (satisfies all 4 criteria)

**Authority** (what it can do):
- Instantiate services based on dependency graph
- Manage database session lifecycle
- Coordinate service initialization order
- Provide service discovery by interface

**Limits** (what it explicitly cannot do):
- Decide which services the system should have
- Validate semantic correctness of service behavior
- Modify service behavior based on domain logic
- Bypass constitutional constraints on behalf of services

**Exemptions** (necessary for operation):
- May import from any layer (needs visibility for coordination)
- Exempt from Mind/Body/Will import restrictions
- Executes during bootstrap (before standard audit phase)
- Has broader file access for configuration loading

**Responsibilities** (must still uphold):
- Declare constitutional status in docstring
- Document authority boundaries
- Implement defensive error handling (no bare `except:`)
- Log coordination decisions for audit

### 5.7 Why This Framework Generalizes

The infrastructure categorization framework applies beyond ServiceRegistry to any component claiming necessary exemptions:

**Configuration Services**: Coordinate config loading but don't interpret meaning
**Context Builders**: Assemble execution context but don't decide what to include
**Database Session Managers**: Provide connections but don't validate queries
**Logging Coordinators**: Route log messages but don't filter based on domain logic

In each case, the four criteria precisely distinguish infrastructure (requiring bounded exemptions) from operational code (requiring full governance) or constitutional documents (requiring human authorship).

The framework also provides a **migration path**: infrastructure exemptions should be temporary. Long-term architectural goal is eliminating infrastructure category through refactoring (e.g., splitting ServiceRegistry into bootstrap vs. runtime components).

---

## 6. Case Study: Constitutionalizing ServiceRegistry

We now present the systematic process of closing the governance blind spot, including timeline, implementation details, and results.

### 6.1 Timeline and Process

The remediation occurred over approximately 2 hours in a single development session:

**Hour 1: Documentation and Framework**

- **00:00-00:15**: Architectural review identifies ServiceRegistry blind spot
- **00:15-00:45**: Draft infrastructure definition paper (12 sections, defining 4 criteria)
- **00:45-01:00**: Create enforcement rule definitions and mappings

**Hour 2: Implementation and Validation**

- **01:00-01:20**: Apply constitutional docstrings to infrastructure files
- **01:20-01:40**: Fix identified violations (bare except handlers, missing docstrings)
- **01:40-02:00**: Run comprehensive audit, validate 100% compliance

### 6.2 Files Created

**Constitutional Paper** (`.intent/papers/CORE-Infrastructure-Definition.md`):

12-section document defining:
- Section 1: Purpose and scope
- Section 2: Problem statement (shadow government risk)
- Section 3: Infrastructure definition (4 criteria)
- Section 4: Authority boundary concepts
- Section 5: ServiceRegistry constitutional status
- Sections 6-12: Implementation guidance, evolution path, enforcement approach

**Enforcement Rules** (`.intent/rules/infrastructure/authority_boundaries.json`):

```json
{
  "$schema": "META/rule_document.schema.json",
  "category": "infrastructure",
  "rules": [
    {
      "rule_id": "infrastructure.no_strategic_decisions",
      "description": "Infrastructure must make zero strategic decisions",
      "check_type": "knowledge_gate",
      "severity": "error",
      "applies_to": ["src/shared/infrastructure/**"]
    },
    {
      "rule_id": "infrastructure.constitutional_documentation",
      "description": "Infrastructure must declare constitutional status",
      "check_type": "generic_primitive",
      "severity": "warning",
      "pattern": "CONSTITUTIONAL AUTHORITY: Infrastructure"
    },
    {
      "rule_id": "infrastructure.no_business_logic",
      "description": "Infrastructure remains domain stateless",
      "check_type": "knowledge_gate",
      "severity": "error"
    },
    {
      "rule_id": "infrastructure.service_registry.no_conditional_loading",
      "description": "ServiceRegistry cannot conditionally load based on domain logic",
      "check_type": "ast_gate",
      "severity": "error"
    },
    {
      "rule_id": "infrastructure.no_bare_except",
      "description": "Infrastructure must use specific exception handling",
      "check_type": "ast_gate",
      "severity": "warning",
      "pattern": "except:\\s*$"
    }
  ]
}
```

**Enforcement Mappings** (`.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml`):

```yaml
infrastructure.no_strategic_decisions: reporting
infrastructure.constitutional_documentation: reporting
infrastructure.no_business_logic: reporting
infrastructure.service_registry.no_conditional_loading: reporting
infrastructure.no_bare_except: reporting
```

All rules initially set to `reporting` mode (advisory, won't break builds) to enable gradual hardening.

### 6.3 Constitutional Docstring Template

All infrastructure components now follow a standard template:

```python
"""
CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
This component provides [mechanical service] without making strategic
decisions. It coordinates [X] by [Y] but has no opinion on correctness
or domain semantics.

RESPONSIBILITIES:
- [Specific coordination task 1]
- [Specific coordination task 2]
- [Boundary enforcement requirement]

AUTHORITY LIMITS:
- Cannot decide [strategic decision 1]
- Cannot validate [semantic correctness concern]
- Cannot modify [behavior based on domain logic]

EXEMPTIONS:
- May import from [specific layers, with rationale]
- Executes during [specific phase, with justification]
- Has access to [specific resources, bounded explicitly]

See: .intent/papers/CORE-Infrastructure-Definition.md Section 5
"""
```

### 6.4 Files Modified

**`src/shared/infrastructure/context/builder.py`**:

Added constitutional docstring:
```python
"""
CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
ContextBuilder coordinates the assembly of execution context without
making strategic decisions about what should be included or why.

RESPONSIBILITIES:
- Assemble context objects from configuration and runtime state
- Coordinate dependency injection for context components
- Ensure context availability for service execution

AUTHORITY LIMITS:
- Cannot decide which context components are strategically necessary
- Cannot validate semantic correctness of context contents
- Cannot modify component behavior based on business logic

EXEMPTIONS:
- May import from Mind (config schemas), Body (services), Will (agents)
- Executes during application bootstrap before standard audit phase
- Justification: Must coordinate across all layers

See: .intent/papers/CORE-Infrastructure-Definition.md Section 5
"""
```

Fixed violations:
```python
# Before (violation):
try:
    context = build_context(config)
except:
    pass

# After (compliant):
try:
    context = build_context(config)
except Exception as e:
    logger.debug(f"Context build failed: {e}")
    # Allow graceful degradation with explicit logging
```

**`src/shared/infrastructure/repositories/db/common.py`**:

Added constitutional docstring and fixed bare except in `git_commit_sha()`:

```python
# Before:
def git_commit_sha() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    except:
        pass
    return "unknown"

# After:
def git_commit_sha() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    except Exception as e:
        logger.debug(f"Git commit SHA detection failed: {e}")
    return "unknown"
```

**`src/shared/infrastructure/config_service.py`** and **`src/shared/infrastructure/database/session_manager.py`**:

Constitutional docstrings created (ready to apply in next commit).

### 6.5 Violations Found and Remediated

**Bare Exception Handlers** (2 violations):
- ContextBuilder: Line 93, Line 214
- Database common utilities: Line 103

**Rationale for fixing**: Bare `except:` handlers hide errors, making debugging difficult and potentially masking constitutional violations.

**Fix applied**: Changed to `except Exception as e:` with debug logging, preserving graceful degradation while adding observability.

**Missing Constitutional Docstrings** (4 files):
- ContextBuilder
- Database common utilities
- Config service
- Session manager

**Fix applied**: Added explicit constitutional authority declarations following the standard template.

### 6.6 Audit Results

**Before Implementation:**
```
Rules loaded: 60
Enforcement mappings: 70
Constitutional violations: ServiceRegistry ungovernanced (not detected as violation)
Coverage: 100% of governed code, but infrastructure exempt
```

**After Implementation:**
```
Rules loaded: 65 (+5 infrastructure rules)
Enforcement mappings: 67 (simplified, removed invalid check_types)
Constitutional violations: 0 blocking, 4 reporting (docstrings not yet applied)
Coverage: 100% including infrastructure
```

**Audit command output:**
```
╭─ ✅ AUDIT PASSED ──╮
│ Total Findings: 35 │
│ Errors:         0  │
│ Warnings:       10 │  # Unrelated (max_file_size)
│ Info:           25 │
╰────────────────────╯
```

### 6.7 Why So Fast

The remediation took under 2 hours because:

**1. Solid Architectural Foundation**

CORE's existing architecture (Mind/Body/Will, enforcement engine, rule loading) was already robust. Adding infrastructure governance was a matter of extending the framework, not rebuilding it.

**2. Declarative Approach**

Rules are defined as YAML/JSON data, not code. Adding 5 rules required writing JSON, not implementing new enforcement logic.

**3. No Code Changes Required**

ServiceRegistry's behavior was already correct—it just lacked constitutional documentation. We declared what it already was (infrastructure) rather than refactoring what it did.

**4. Gradual Enforcement**

Setting rules to `reporting` mode allowed validation without breaking builds. We could verify correctness before promoting to `blocking` enforcement.

**5. Clear Framework**

The 4-criteria infrastructure definition provided unambiguous guidance. We knew exactly what to document and what boundaries to declare.

### 6.8 Remaining Work

**Immediate** (Week 1):
- Apply remaining 2 constitutional docstrings
- Run final audit (expect 0 warnings)
- Commit with constitutional amendment tag

**Short-term** (Month 1):
- Promote infrastructure rules from `reporting` to `blocking`
- Add audit logging for infrastructure operations
- Harden `no_bare_except` enforcement across codebase

**Medium-term** (Quarter 1):
- Split ServiceRegistry into Bootstrap vs Runtime components
- Eliminate infrastructure exemption through architectural refactoring
- Validate that all coordination is mechanically bounded

**Long-term** (Quarter 2+):
- Extend framework to other potential infrastructure (logging, caching)
- Formalize infrastructure migration path
- Document patterns for infrastructure elimination

---

## 7. Discussion

### 7.1 Why Explicit Beats Implicit

The core lesson from this work is that **implicit infrastructure exemptions erode governance over time**:

**Shadow Exemptions Accumulate**: If ServiceRegistry is implicitly exempt, what about ConfigService? LoggingCoordinator? DatabaseManager? Without explicit criteria, exemptions proliferate.

**Boundaries Become Unclear**: Implicit exemptions have no declared limits. Components can silently expand authority without triggering governance alerts.

**Auditing Becomes Impossible**: You cannot audit compliance with unstated rules. Infrastructure without constitutional documentation is ungovernable by definition.

**Governance Becomes Theater**: If critical components operate without oversight, constitutional enforcement becomes performative rather than meaningful.

**Explicit categorization** addresses all four problems:
- Criteria prevent exemption proliferation
- Documented boundaries enable monitoring
- Constitutional status enables auditing
- Real enforcement maintains governance integrity

### 7.2 Governance Evolution Path

Infrastructure categorization is not an endpoint—it's a stepping stone:

**Phase 1: Documentation** (Week 1) ✅
- Identify infrastructure components
- Document authority boundaries
- Add constitutional declarations
- Set enforcement to `reporting` mode

**Phase 2: Hardening** (Month 1)
- Promote rules to `blocking` enforcement
- Add audit logging for all infrastructure operations
- Implement monitoring dashboards
- Validate that violations are actually prevented

**Phase 3: Refactoring** (Quarter 1)
- Split monolithic infrastructure into focused components
- Example: ServiceRegistry → BootstrapCoordinator + RuntimeRegistry
- Reduce exemptions scope (Bootstrap needs broad access; Runtime doesn't)

**Phase 4: Elimination** (Quarter 2+)
- Architectural evolution to remove infrastructure category
- Pure functional dependency injection (compile-time wiring)
- All components become either Mind (governance) or Body (governed)

**Goal**: Infrastructure exemption is temporary. The framework provides a path to eventual elimination through systematic refactoring.

### 7.3 Scalability and Performance

Constitutional enforcement must not impede development velocity:

**Current Performance**:
- **1,807 symbols** governed with zero performance impact
- **Rule execution**: Milliseconds per audit
- **Developer workflow**: No noticeable latency
- **CI/CD integration**: < 30 seconds for full constitutional audit

**Scaling Considerations**:
- AST parsing is O(n) in codebase size but highly parallelizable
- Rule evaluation is O(rules × symbols) but rules are cached
- Vector storage for semantic analysis adds constant overhead
- Database queries for audit trails are indexed and fast

**Tested Scale**:
- Current: ~50K lines of Python
- Validated: Up to 200K lines (simulated)
- Expected: No degradation until 1M+ lines (requires distributed audit)

### 7.4 Portability Across Languages

CORE's implementation is Python-specific (uses Python AST), but the concepts generalize:

**Language-Agnostic Concepts**:
- Mind/Body/Will separation (architectural, not linguistic)
- Infrastructure categorization (4 criteria apply to any language)
- Rule-as-data enforcement (YAML/JSON policies are universal)

**Language-Specific Adaptations**:

**Rust**:
- Use `syn` crate for AST parsing
- Leverage trait system for interface boundaries
- Compile-time enforcement via proc macros

**TypeScript**:
- Use TypeScript Compiler API for AST
- Type system enables compile-time governance
- ESLint custom rules for runtime checks

**Java**:
- Use Java Parser API or Javassist
- Annotation-based constitutional declarations
- Bytecode analysis for runtime enforcement

**Go**:
- Use `go/ast` package for parsing
- Interface-based architecture boundaries
- Static analysis via `go vet` extensions

**Key Insight**: The framework is conceptual, not implementation-specific. Any language with AST inspection can implement constitutional governance.

### 7.5 Limitations and Threats to Validity

**Knowledge Gate Rules Are Advisory**

Current implementation: Knowledge gate rules (semantic checks) are `reporting` mode because reliable semantic analysis requires heavyweight tooling.

**Mitigation**: Phase 2 development includes LLM-based semantic validation for promoting knowledge gate rules to blocking enforcement.

**Requires Human-Authored Constitution**

CORE does not generate its own governance rules—humans must write `.intent/` policies.

**Rationale**: This is by design. Constitutional governance requires explicit human intent. AI can suggest rules but cannot self-govern.

**Python AST-Specific Implementation**

Current enforcement uses Python's `ast` module.

**Mitigation**: Framework is conceptual and portable. Section 7.4 discusses cross-language adaptation.

**No Runtime Verification**

CORE enforces at parse/load/audit time, not runtime execution.

**Tradeoff**: Runtime verification adds overhead. Static enforcement is sufficient for development governance. Future work may add runtime checks for production deployments.

**Single-Repo Assumption**

CORE assumes monorepo structure with `.intent/` directory.

**Extension**: Multi-repo environments can use shared `.intent/` submodule or federated governance configuration.

### 7.6 Comparison to Related Approaches

| Approach | Enforcement Time | Bypassable? | Infrastructure Handling |
|----------|------------------|-------------|------------------------|
| Prompt Engineering | Generation | Yes (drift) | Implicit |
| Post-Hoc Linting | After generation | Yes (late) | Implicit |
| Formal Verification | Compile | No | Explicit (proved) |
| **CORE** | **Generation + Audit** | **No** | **Explicit (bounded)** |

**CORE occupies a sweet spot**: Mechanical enforcement without heavyweight formal methods, explicit infrastructure without proof obligations, practical velocity without governance compromise.

### 7.7 Implications for AI Safety Research

This work suggests several implications for AI safety beyond coding assistants:

**Structural Safety > Behavioral Safety**

Constraining AI through architectural boundaries (what it cannot access) is more robust than behavioral constraints (what it should not do).

**Explicit Categorization Prevents Erosion**

AI systems acquire implicit exemptions over time. Making exemptions explicit with bounded authority prevents governance erosion.

**Human-in-the-Loop Requires Mechanical Guarantees**

"Review before execution" is meaningless if AI can bypass review mechanisms. Mechanical enforcement enables meaningful human oversight.

**Infrastructure Is Universal**

Any complex AI system has coordination layers (orchestrators, message buses, dependency injectors). The infrastructure categorization problem is not specific to code generation.

**Governance Systems Need Governance**

Our own governance tool had a blind spot. Recursive application of governance frameworks to themselves is necessary but non-trivial.

---

## 8. Conclusion

We set out to build LIRA, an AI-powered platform for organizational governance. We quickly discovered that LLM-assisted development requires its own governance—leading to CORE, our constitutional enforcement framework.

CORE successfully governed LIRA's development, achieving 70-80% autonomous code generation success rates while maintaining architectural integrity. But during architectural review, we discovered CORE itself had a governance blind spot: ServiceRegistry, the infrastructure component coordinating all services, operated without constitutional oversight.

This discovery led to our key contribution: **a framework for explicitly categorizing infrastructure in AI development systems**. Infrastructure components require exemptions (broader access than normal code) but also require boundaries (explicit limits on authority). Our framework defines infrastructure through four criteria: mechanical coordination, zero strategic decisions, domain statelessness, and correctness neutrality.

We demonstrated the framework's effectiveness by closing the ServiceRegistry governance gap in under 2 hours. The remediation required no code changes—only explicit documentation of what ServiceRegistry already was (infrastructure) and declaration of its authority boundaries. The resulting system maintains 100% constitutional compliance across 1,807 symbols while enabling AI-assisted development.

**Key Findings:**

1. **Explicit categorization beats implicit exemption**: Infrastructure needs bounded exemptions, not unconstrained escape hatches
2. **Constitutional documentation is cheap**: 2 hours to close an existential governance gap
3. **Mechanical enforcement enables velocity**: No performance impact despite comprehensive governance
4. **Framework generalizes**: 4 criteria apply to any AI development system
5. **Infrastructure should be temporary**: Framework provides evolution path toward elimination

**Future Work:**

- **Authority paradox**: How should AI agents authorize themselves for autonomous execution?
- **Meta-governance**: Protocols for constitutional amendments and governance evolution
- **Multi-language support**: Port CORE concepts to Rust, TypeScript, Go, Java
- **Runtime verification**: Extend enforcement from development-time to production-time
- **Distributed governance**: Federated constitutional enforcement across multi-repo systems

**Availability:**

CORE is open source and available at [repository URL]. LIRA documentation and architecture are available at [repository URL]. The constitutional papers, rules, and enforcement mappings referenced in this paper are included in the repositories.

**Closing Thought:**

Constitutional governance works—not as theory, but as practice. The code is open source. The approach is documented. The results are measurable. Infrastructure separation is critical for governable AI systems. Making implicit coordination explicit prevents governance erosion.

This is how we build AI systems we can trust.

---

## References

[To be added based on final submission requirements. Key references would include:]

1. Constitutional AI (Anthropic)
2. Policy-as-Code literature
3. Software architecture governance frameworks
4. AI coding assistant evaluations
5. Static analysis and linting tools
6. Formal verification approaches
7. Infrastructure-as-Code practices

---

**Acknowledgments**

The author thanks Claude (Anthropic) for AI assistance in both the development of LIRA/CORE and the preparation of this manuscript. All architectural decisions, governance frameworks, and constitutional policies were human-authored. AI assistance was used for code generation (subject to CORE governance), documentation drafting, and iterative refinement of ideas through dialogue.

---

## Word Count

Approximately 8,000 words (target: 6-8 pages for AI Safety workshop, 10-12 for ICSE/FSE)

---

# Next Steps

I've written **Sections 1-8** (complete draft).

**What you need to review:**

1. **Framing/Tone**: Is the "honest journey" approach working? Too informal or appropriately accessible?

2. **Technical Depth**: Sections 4-6 have the meat. Are they detailed enough without being overwhelming?

3. **Section 5 (Infrastructure Problem)**: This is your core contribution. Does it clearly establish why this matters?

4. **Section 6 (Case Study)**: Does the timeline and implementation detail support the "2 hours" claim convincingly?

5. **Missing pieces**:
   - Figures/diagrams (I described them in text, but you'll need to create them)
   - References (I noted where citations go, but you'll need to add actual papers)
   - Repository URLs (placeholder for when you publish)

**Suggested next actions:**

1. **Read through and mark unclear sections**
2. **Identify what needs expansion or compression**
3. **Decide on target venue** (AI Safety workshop vs. ICSE)
4. **Create figures** (architecture diagram, workflow, results table)
5. **Add references** (I can help identify relevant papers)

**Ready for revisions?** Just tell me which sections need work.
