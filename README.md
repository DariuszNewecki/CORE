CORE — Architectural Integrity for AI-Era Development

CORE prevents architectural drift by automatically detecting when your code violates your project's design rules, ensuring safe, governed, and AI-driven software development.
The Problem
Every codebase eventually suffers from architectural decay:

New features bypass established patterns
Dependencies creep across module boundaries
Design documents become outdated fiction
Code reviews miss structural violations

Traditional tools like linters catch syntax errors but miss architectural ones. CORE fills this gap with AI-powered governance and constitutional compliance.
The Solution in 30 Seconds

Define your rules in machine-readable YAML files (.intent/ directory)
Write code normally using your existing workflow
Run make audit to check architectural compliance
Get actionable feedback on violations with suggested fixes

# Example audit output
❌ Domain Violation: src/api/user.py
   Problem: 'api' domain imported 'database.models'
   Rule: API layer should only import from 'services'
   Fix: Move database logic to UserService class

See It Work (5-minute demo)
Try the Worked Example to see CORE catch a real violation. This tutorial shows you how to:

Create a governed project with one command
Intentionally break an architectural rule
Watch CORE's auditor detect and explain the violation

Visualizing CORE's Architecture
CORE's unique "Mind-Body-Will" architecture ensures governance and safety:
+-----------------+
|     Mind        |  YAML/JSON files (.intent/) define rules, principles, and knowledge
| (Constitution)  |
+-----------------+
          |
          v
+-----------------+
|     Will        |  AI agents (LLMs) reason and plan based on the Mind
| (AI Reasoning)  |
+-----------------+
          |
          v
+-----------------+
|     Body        |  Python code (src/) executes plans, audited for compliance
| (Codebase)      |
+-----------------+
          |
          v
[Constitutional Auditor]  Ensures Body aligns with Mind via continuous checks

This structure, backed by cryptographic signing and canary checks, guarantees safe evolution of your codebase.
Installation & Quick Start
Requirements: Python 3.12+, Poetry, Git
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your LLM API keys (see .intent/config/runtime_requirements.yaml)

# Verify installation
make check

# Create your first governed project
poetry run core-admin new my-app --profile default

# Run your first audit
cd work/my-app && make audit

Troubleshooting Tip: If core-admin fails, ensure Poetry's virtualenv is activated (poetry shell) or prefix with poetry run. Check logs in reports/ for details.
When to Use CORE
CORE is ideal for:

Teams prioritizing architectural consistency and long-term maintainability
Complex systems with clear domain boundaries (e.g., microservices, enterprise apps)
Projects requiring traceable, auditable changes (e.g., regulated industries)
Developers leveraging AI safely with governance constraints

CORE might be overkill if:

You're building simple scripts or throwaway prototypes
Your team relies solely on manual reviews
You prefer implicit, undocumented architectural guidelines

How It Works
CORE uses three components:

Mind (.intent/): YAML/JSON files defining your project's architectural rules, principles, and knowledge graph.
Body (src/): Your application logic, organized into domains (e.g., core, agents).
Will (AI Layer): LLM-driven agents (e.g., PlannerAgent) that reason, plan, and generate code, constrained by the Mind.

The Constitutional Auditor runs continuously, catching:

Cross-domain import violations
Missing capability tags (# CAPABILITY:)
Inconsistent code patterns
Breaches of safety policies (e.g., direct .intent/ writes)

Changes are cryptographically signed and validated via a "canary check" to ensure safety before application.
Integration with Existing Projects
Add CORE to any codebase with the Bring Your Own Repo (BYOR) feature:
# Analyze your project and propose a constitution
poetry run core-admin byor-init /path/to/your/project

# Apply the constitution
poetry run core-admin byor-init /path/to/your/project --write

# Run an audit
cd /path/to/your/project && make audit

Example: Convert a Flask app to a CORE-governed project and enforce domain boundaries.
Project Status
CORE is an Architectural Prototype (v0.2.0) with a stable constitutional governance system. It achieves A0 (Observe) and is progressing toward A1 (Propose) on the Autonomy Ladder. Current focus: enhancing AI agent capabilities for autonomous app generation (see Roadmap).
We're making CORE public to collaborate on AI-governed software development. Try generating a sample app or auditing your project!
Documentation

What is CORE?: Philosophy and context
Architecture Guide: Technical details
Governance Model: Constitutional amendment process
Starter Kits: Pre-packaged project templates
Contributing Guide: How to contribute

Glossary:

Mind: The .intent/ directory, your project's "constitution" (rules, principles).
Body: The src/ directory, your executable code.
Will: AI agents (LLMs) that reason and act within constitutional constraints.
Canary Check: A safety mechanism testing changes in an isolated environment.
Knowledge Graph: A map of your code's symbols and capabilities.

Comparison to Other Tools



Tool
Purpose
CORE's Difference



ESLint, Pylint
Syntax/style checking
Enforces architectural and domain rules


SonarQube
Code quality metrics
Constitutional alignment and traceability


ArchUnit
Architecture testing
AI-driven analysis with natural language fixes


GitHub Copilot
Code completion
Governed development with safety constraints


AutoGPT
Autonomous task execution
Structured, safe, and auditable code changes


CORE is an AI architect, not just a code generator, ensuring long-term maintainability.
Contributing
Join us to shape AI-governed software! See CONTRIBUTING.md for details. Key areas:

AI Agents: Enhance PlannerAgent for autonomous app generation (Roadmap Phase 3).
Policies: Develop new safety or architectural rules.
Toolchain Integration: Add support for other linters or CI systems.
Examples: Create sample governed apps (e.g., REST APIs, CLI tools).
Docs: Add diagrams, tutorials, or simplify for beginners.

Get Started: Fork the repo, run make format, and open a PR for a docstring fix or audit enhancement.
License
MIT License - see LICENSE for details.