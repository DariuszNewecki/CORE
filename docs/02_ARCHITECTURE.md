02_ARCHITECTURE.md
The CORE Architecture
Quick Start for New Users
The "Mind-Body Problem" is simple:
Rules (The Mind) are kept separate from the code (The Body) to maintain order and prevent architectural drift.
An automated Auditor constantly checks that the code follows the rules.
👉 Start with the Worked Example to see these directories in action and watch the Auditor catch a rule violation.
The Mind-Body Problem, Solved
CORE's architecture strictly separates the project's intent from its implementation.
The Mind (.intent/) is the source of truth. It declares what the system should do and why. It contains all policies, goals, and knowledge.
The Body (src/) is the machinery. It contains the Python code that performs actions but does not make decisions.
The Bridge is the ConstitutionalAuditor. It ensures the Body never violates the rules declared in the Mind.
Anatomy of the Mind (.intent/)
This is your project's constitution, containing all its rules and self-knowledge.
Directory	Purpose	Key Files
/mission	The project's ultimate goals	principles.yaml
/policies	Enforceable rules for code & agents	safety_policies.yaml
/knowledge	The system's map of its own code	knowledge_graph.json
/constitution	The process for making changes	approvers.yaml
/proposals	Drafts of proposed changes	cr-*.yaml
/config	Environment & runtime requirements	runtime_requirements.yaml
/schemas	The structure all other files follow	*.schema.json
Anatomy of the Body (src/)
The Body is organized into distinct domains, each with a single responsibility, as defined in source_structure.yaml.
Directory	Domain	Responsibility
/core	core	The application's main loop, API server, and core services.
/agents	agents	Specialized AI actors (e.g., Planner, Coder, Reviewer).
/system	system	Governance tools, including the Auditor and the core-admin CLI.
/shared	shared	Utilities and data models used by all other domains.
Architectural Enforcement: The ConstitutionalAuditor reads source_structure.yaml and will fail the build if any code file makes a forbidden import (e.g., if the core domain tries to import directly from system).
Takeaways
The architecture enforces a scalable and maintainable separation of concerns.
The system's self-knowledge (knowledge_graph.json) is generated directly from the source code, ensuring it is never out of date.
Next: Read about the Governance Model to understand how changes are made safely.
