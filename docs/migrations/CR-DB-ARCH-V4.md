# Constitutional Amendment Proposal: The Layered, DB-Driven Architecture (CR-DB-ARCH-V4)

- **ID**: CR-DB-ARCH-V4
- **Status**: DRAFT
- **Author**: AI Systems Architect
- **Principle Alignment**: `separation_of_concerns`, `single_source_of_truth`, `clarity_first`

## 1. Justification (`reason_with_purpose`)

This proposal ratifies a new layered architecture that clarifies the role of every component and establishes the **Database as the single source of truth for operational state**. It resolves architectural drift by creating a governable, scalable, and clear structure for all current and future development, including the system's autonomous agents.

## 2. Target Directory Structure (`clarity_first`)

This structure introduces a new, canonical home for the system's "Will"—the AI Agents—within the orchestration layer.

```text
src/
├── api/
│   └── v1/
├── cli/
│   └── commands/
├── core/                 # Orchestration Layer
│   ├── agents/           # <<-- HOME FOR THE "WILL"
│   │   ├── planner_agent.py
│   │   └── execution_agent.py
│   └── invokers/
│       └── capability_invoker.py
├── features/             # Business Capabilities
│   └── introspection/
│       └── service.py
├── services/             # Infrastructure Services
│   ├── clients/
│   └── repositories/
├── shared/               # Foundational Utilities
│   ├── models/
│   └── config.py
└── system/               # Governance (Not used at runtime)
    └── governance/
```

### Constitutional Mandates
- **Agents are Orchestrators**: All agent logic (PlannerAgent, ExecutionAgent, etc.) MUST reside in `src/core/agents/`.
- **Agents Use Capabilities**: Agents MUST NOT contain business logic. They orchestrate calls to `features/` and `services/` via the CapabilityInvoker.

## 3. Constitutional Impact

### 3.1. Database as SSOT
The `core.capabilities` table remains the canonical registry of all system capabilities.

### 3.2. Enforceable Import Contracts (`source_structure.yaml`)
The import contracts are updated to reflect the agent's position in the architecture.