Contributing to CORE
Thank you for considering a contribution to CORE! This project pioneers self-governing software through a unique constitutional framework, and every contribution—from bug reports to philosophical discussions—is vital to its evolution.
This guide outlines how you can get involved, whether you're a coder, architect, or documentation enthusiast.
The Philosophy: Principled Contributions
CORE is governed by a machine-readable "constitution" in the .intent/ directory. All contributions must align with its principles, particularly clarity_first, which prioritizes making the system easier to understand. Before contributing, please read:

README.md: High-level vision and a 5-minute demo.
The CORE Philosophy (docs/01_PHILOSOPHY.md): Deep dive into the Mind-Body-Will architecture.
The Governance Model (docs/03_GOVERNANCE.md): How safe, auditable changes are made to the constitution.

Contribution Workflow Overview
+---------------------------------+
| 1. Read Docs & Roadmap          |
|   Understand CORE's principles  |
+---------------------------------+
                |
                v
+---------------------------------+
| 2. Choose Contribution Type     |
|   - Bug Report                  |
|   - Docs Improvement            |
|   - Code (Tests, Features)      |
|   - Constitutional Proposal     |
+---------------------------------+
                |
                v
+---------------------------------+
| 3. Submit via GitHub            |
|   Fork, Branch, PR, Run Checks  |
|   Ensure `make check` passes    |
+---------------------------------+

How You Can Contribute
There are many ways to contribute, and most don't require coding expertise.
🏛️ Discussing Architecture and Governance
The most impactful contributions are ideas that shape CORE's architecture and governance. These align with our Roadmap (docs/04_ROADMAP.md), targeting the v1.0 Epic for a policy-driven cognitive layer.

Review the Roadmap: Explore open challenges (e.g., implementing cognitive_roles.yaml for AI roles). Share thoughts via GitHub Issues.
Propose Constitutional Changes: Suggest improvements to principles or policies (e.g., new safety rules). Open an issue to discuss, then draft a proposal in .intent/proposals/. See Governance Model for the process.
Example Task: Propose a new safety policy for secrets management in .intent/policies/safety_policies.yaml.

🐞 Reporting Bugs
Help strengthen CORE's ConstitutionalAuditor by reporting bugs or inconsistencies. A great bug report includes:

The command run (e.g., poetry run core-admin byor-init .).
Full output, including errors and tracebacks.
Your hypothesis on the cause.

Example: If the auditor misses an illegal import, report it to improve the "immune system."
✍️ Improving Documentation
Clear docs are critical to CORE's clarity_first principle. If you find unclear, outdated, or missing documentation:

Submit a PR to fix typos, clarify concepts, or add examples.
Suggest visuals (e.g., diagrams for architecture).
Beginner Task: Add a docstring to an undocumented function in src/system/tools/ or improve a tutorial in docs/.

💻 Contributing Code
Code contributions are welcome but must adhere to CORE's strict governance.
1. Code Conventions
To ensure clarity_first:

Formatting: Use black (run make format to auto-format).
Linting: Enforce quality with ruff (included in make check).
Typing: All functions/methods must have type hints.
Docstrings: Every public module, class, function, and method needs a clear docstring.
Capability Tags: Add # CAPABILITY: <name> comments for key functions (see project_manifest.yaml).

2. Architectural Principles
CORE enforces separation_of_concerns via domains:

Domains (e.g., core, agents) are defined in .intent/knowledge/source_structure.yaml.
Import rules: Only import from allowed_imports in that file. The ConstitutionalAuditor enforces this.
Note: Propose constitutional changes before adding new cross-domain imports.

3. Dependency Management
CORE uses Poetry:

Add dependencies: poetry add <package_name>.
Add dev dependencies: poetry add --group dev <package_name>.
Install: Run poetry install to set up the environment.

Troubleshooting: If Poetry fails, ensure Python 3.12+ is used and check .env for required LLM API keys.
4. Testing
Tests are critical to CORE's safety. Write tests for new code:

Unit tests: tests/unit/ (e.g., test_git_service.py).
Integration tests: tests/integration/ (e.g., test_full_run.py).
Governance tests: tests/governance/ (e.g., test_local_mode_governance.py).
Goal: Aim for 80%+ code coverage (check with pytest --cov).
Run tests: make test or poetry run pytest.

5. Submission Workflow

Find or open an issue on GitHub to discuss your contribution.
Fork the repo and create a branch (e.g., feat/add-cognitive-service).
Write code, adhering to conventions.
Run checks:
Quick checks: make fast-check (linting + unit tests).
Full audit: make check (includes constitutional audit).
Fix formatting: make format.


Submit a pull request (PR) with a clear description linking to the issue.

Debugging Tip: If make check fails, check reports/drift_report.json for details on violations (e.g., illegal imports).
Example Code Contributions

Add a test case for symbol_processor.py to handle invalid ASTs.
Implement CognitiveService in src/core/ for the v1.0 Epic (see Roadmap Phase 2).
Create a new starter kit in src/system/starter_kits/ for a REST API.

Why Contribute?
Your contributions shape the future of AI-governed software development. Whether you fix a typo, propose a safety policy, or build a new agent, you're helping CORE achieve its North Star: autonomous, safe software creation.
Get Started: Try a small task, like adding a capability tag to a function in src/, and run make check to verify compliance.
Questions?
Join the discussion on GitHub Issues or reach out via the project's community channels (TBD). We're excited to build this future with you!