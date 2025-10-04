01_PHILOSOPHY.md
1. The CORE Philosophy
The Prime Directive
CORE exists to transform human intent into complete, evolving software systems — without the usual decay into architectural drift, duplication, and degradation.
It achieves this by governing itself with a machine-readable constitution, ensuring that all development, whether performed by humans or AI, is safe, transparent, and aligned with its declared purpose.
The Architectural Trinity: Mind, Body, and Will
To ensure safety and clear separation of concerns, CORE's design is a simple trinity:
🏛️ The Mind (.intent/): The Constitution. A collection of YAML/JSON files that define the project's rules, goals, and self-knowledge. It answers what the system should be and why.
🦾 The Body (src/): The Machinery. Simple, reliable Python code and tools that perform actions like writing files or running tests. The Body's job is to do, not to think.
🧠 The Will (AI Agents): The Reasoning Layer. A set of specialized AI agents that read the Mind and use the Body's tools to achieve the declared goals.
This separation is enforced by an automated ConstitutionalAuditor that continuously verifies the Body's compliance with the Mind.
code
Mermaid
graph TD
    subgraph core[CORE System]
        Mind[🏛️ Mind: .intent/ Rules] --> Will[🧠 Will: AI Agents]
        Will --> Body[🦾 Body: src/ Code]
    end

    Body -- "State of the Code" --> Auditor[ConstitutionalAuditor]
    Auditor -- "Compliance Report" --> Mind
The Ten-Phase Loop of Reasoned Action
To prevent reckless changes, every significant autonomous action in CORE follows a deliberate "think-plan-do-check" cycle. This ensures every change is traceable to a purpose and is validated against the constitution.
GOAL: A human operator provides a high-level request.
WHY: The system links the goal to a core constitutional principle (e.g., safe_by_default).
INTENT: The goal is formalized into a machine-readable plan.
AGENT: The right AI agent (e.g., Planner, Coder) is selected for the job.
MEANS: The agent consults the Body's known capabilities to see what tools it can use.
PLAN: The agent creates a detailed, step-by-step sequence of actions.
ACTION: The plan is executed by the Body's tools.
FEEDBACK: The ConstitutionalAuditor and test suite verify the change for compliance.
ADAPTATION: If feedback is negative, the AI attempts to self-correct the change.
EVOLUTION: The Mind's knowledge is updated to reflect the new state of the system.
code
Mermaid
graph TD
    A[1. Goal] --> B[2. Why]
    B --> C[3. Intent]
    C --> D[4. Agent]
    D --> E[5. Means]
    E --> F[6. Plan]
    F --> G[7. Action]
    G --> H[8. Feedback]
    H --> I[9. Adaptation]
    I --> J[10. Evolution]
    J -.-> A
Takeaways
CORE is architected for deliberate, safe, and auditable change.
The separation of Mind, Body, and Will is the core safety mechanism.
Next: See the Architecture Document for technical details on these components.
