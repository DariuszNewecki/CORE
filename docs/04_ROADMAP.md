04_ROADMAP.md
The CORE Project Roadmap
For New Users: Where CORE Is Going
CORE is evolving from a system that audits code (A0) into a conversational AI architect (A4) that builds apps from your ideas.
The foundational governance layer is complete.
Our roadmap now focuses on two major epics:
v1.0: The Self-Evolving Architect – Making the system's AI reasoning smarter and more efficient.
v1.2: The Governed Capability System – A recently completed epic that refactored the system's core knowledge representation.
👉 You can help! Check out the Next Up phase in the tables below for great contribution opportunities.
Preamble: From Foundation to Self-Evolution
The project has a stable foundation for audits and governance.
The core logic for the policy-driven AI layer (Mind/Body/Will) is implemented.
With the completion of the conversational chat command, the system can now translate natural language into structured goals.
The next steps focus on making the system's reasoning more dynamic and its user interface more accessible.
📄 Historical work: docs/archive/StrategicPlan.md
Epic v1.0: The Self-Evolving Architect
Goal: Build a self-evolving system that understands non-coders’ ideas and optimizes AI usage without hardcoded limits.
Roadmap Phases (v1.0)
Phase	Challenge	Goal	Status	Opportunity	ETA
1: Constitution	Implicit AI roles in code	Define cognitive_roles.yaml for roles like Planner, Coder	✅ Completed	Refine roles or propose new specialized agents (e.g., TestWriter).	Completed Q3 2024
2: Machinery	Body has AI logic	Build simple CognitiveService to read roles	✅ Completed	Optimize the CognitiveService for performance or caching.	Completed Q3 2024
3: Agents	Agents use hardcoded clients	Refactor agents to use CognitiveService	✅ Completed	Improve the agent reasoning loop in run_development_cycle.	Completed Q3 2024
4: Cleanup	Obsolete classes	Remove old BaseLLMClient; update runtime_requirements.yaml	⏳ Planned	Great first-time contributor task: remove src/core/clients.py.	Q4 2024
5: Conversational Access	CLI limits non-coders	Add IntentTranslator agent and core-admin chat command	✅ Completed	Improve intent_translator.prompt for more complex queries.	Completed Q3 2024
6: Dynamic Deduction	Static LLM assignments	Add DeductionAgent + policy to optimize LLM choices	✅ Completed	Refine deduction_policy.yaml scoring weights for different tasks.	Completed Q3 2024
Epic v1.1: The Accessible Operator (Completed)
Goal: Dramatically improve the accessibility and discoverability of CORE's capabilities by unifying all user actions into a single core-admin entrypoint with an optional interactive menu.
Roadmap Phases (v1.1)
Phase	Challenge	Goal	Status	Opportunity	ETA
1: Consolidation	Multiple entry points (make, tools/, scripts)	Migrate all legacy tool logic into scriptable core-admin command groups	✅ Completed	N/A	Completed Q4 2024
2: Discoverability	Poor command visibility	Implement a richly formatted, grouped help screen for core-admin --help	⏳ Planned	Design the layout and grouping for the new help text.	Q2 2025
3: Accessibility	High cognitive load for new users	Build an interactive, menu-driven TUI that launches on core-admin	✅ Completed	Suggest improvements to the menu flow or wording in interactive.py.	Completed Q3 2024
4: API Clarity	Undefined API purpose	Create docs/10_API_REFERENCE.md to formalize the API for machine use	▶️ Next Up	Great documentation task for a beginner.	Q1 2025
Epic v1.2: The Governed Capability System (Completed)
Goal: Address significant architectural debt by migrating the monolithic capability_tags.yaml to a decentralized, domain-driven system.
This improves scalability, reduces developer friction, and enables more robust governance.
Roadmap Phases (v1.2)
Phase	Challenge	Goal	Status	Opportunity	ETA
1: Discovery	Single point of failure	Analyze existing tags and design the new decentralized schema	✅ Completed	N/A	Completed Q3 2024
2: Migration	Risk of breaking changes	Implement a dual-format loader and migrate capabilities domain by domain	✅ Completed	N/A	Completed Q3 2024
3: Finalization	Legacy code	Deprecate the old monolithic file and update all tools to use the new system	✅ Completed	N/A	Completed Q3 2024
📄 Full Plan: docs/migrations/MIGRATION_GUIDE_CAPABILITY_TAGS.md
Future Phases (Post-v1.1)
Phase	Goal	ETA
Web Interface & DB	Evolve the unified CLI/API to a web UI with DB backing for full accessibility	Q3 2025
Historical Roadmap (v0.2.0 – Completed)
✅ Scaling Constitution
✅ Autonomous MVP
✅ Self-Improvement
✅ Robustness
✅ Architectural Health
Takeaways
The architectural refactoring of the capability system (Epic v1.2) is complete.
The consolidation of the CLI (Epic v1.1) is complete.
The major AI reasoning work from the v1.0 epic is complete.
The next major user-facing task remains Phase 1.1.4: API Clarity.
The project is on track for a v1.1 release in Q1 2025.
Contribute
Developer experience: The documentation task in Phase 1.1.4 (API Clarity) is a perfect first issue.
Beginners: Phase 1.0.4 (Cleanup) is a great, well-defined first issue to tackle.
✅ Check GitHub issues to get started.
