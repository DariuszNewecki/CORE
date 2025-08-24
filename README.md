# CORE — Architectural Integrity for AI-Era Development

[![Status: Architectural Prototype](https://img.shields.io/badge/status-architectural%20prototype-blue.svg)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CORE prevents architectural drift by automatically detecting when your code violates your project's design rules.**

## The Problem

Every codebase eventually suffers from architectural decay:
- New features bypass established patterns
- Dependencies creep across module boundaries  
- Design documents become outdated fiction
- Code reviews miss structural violations

Traditional tools catch syntax errors but miss architectural ones. CORE fills that gap.

## The Solution in 30 Seconds

1. **Define your rules** in machine-readable files (`.intent/` directory)
2. **Write code normally** using your existing workflow
3. **Run `make audit`** to check architectural compliance
4. **Get specific feedback** on violations with suggested fixes

```bash
# Example audit output
❌ Domain Violation: src/api/user.py
   Problem: 'api' domain imported 'database.models' 
   Rule: API layer should only import from 'services'
   Fix: Move database logic to UserService class
```

## See It Work (5-minute demo)

The fastest way to understand CORE is to see it catch a real violation:

**[→ Try the Worked Example](docs/09_WORKED_EXAMPLE.md)**

This tutorial shows you how to:
1. Create a new governed project with one command
2. Intentionally break an architectural rule  
3. Watch CORE's auditor detect and explain the violation

## Installation & Quick Start

**Requirements:** Python 3.11+ and Poetry

```bash
# Install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Set up environment
cp .env.example .env
# Edit .env with your LLM API keys

# Verify installation
make check

# Create your first governed project
poetry run core-admin new my-app --profile default
```

## When to Use CORE

**CORE is valuable when:**
- You work on teams where architectural consistency matters
- You're building complex systems with clear domain boundaries
- You want automated enforcement of design decisions
- You need traceability for architectural changes

**CORE might be overkill if:**
- You're building simple scripts or prototypes
- Your team is comfortable with manual code reviews only
- You prefer implicit architectural guidelines

## How It Works

CORE uses three components:

- **The Mind (`.intent/` directory):** Your project's architectural rules, written in YAML
- **The Body (`src/` code):** Your actual application logic
- **The Auditor:** AI-powered analysis that ensures Body follows Mind's rules

The auditor runs continuously, catching violations like:
- Cross-domain imports that violate boundaries
- Missing capability documentation
- Inconsistent code patterns
- Violations of custom architectural policies

## Integration with Existing Projects

Add CORE to any existing codebase:

```bash
# Analyze your project and suggest initial rules
poetry run core-admin byor-init /path/to/your/project

# Apply the suggested constitution  
poetry run core-admin byor-init /path/to/your/project --write

# Run your first audit
cd /path/to/your/project && make audit
```

## Project Status

CORE is an architectural prototype with a stable core and active development. The constitutional governance system is complete and tested. Current focus is expanding AI agent capabilities for autonomous development workflows.

We're making this public to collaborate on the foundational architecture for AI-governed software development.

## Documentation

- **[What is CORE?](docs/00_WHAT_IS_CORE.md)** - Philosophy and deeper context
- **[Architecture Guide](docs/02_ARCHITECTURE.md)** - Technical implementation details  
- **[Governance Model](docs/03_GOVERNANCE.md)** - How constitutional changes work
- **[Contributing Guide](CONTRIBUTING.md)** - How to get involved

## Comparison to Other Tools

| Tool | Purpose | CORE's Difference |
|------|---------|-------------------|
| ESLint, Pylint | Syntax and style checking | Architectural and domain boundary enforcement |
| SonarQube | Code quality metrics | Constitutional alignment and intent traceability |
| ArchUnit | Architecture testing | AI-powered analysis with natural language explanations |
| GitHub Copilot | Code completion | Governance-first development with constitutional constraints |

## Contributing

We welcome contributions from AI engineers, DevOps professionals, and governance experts. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidelines.

Key areas for contribution:
- AI agent capabilities
- Constitutional policy templates
- Integration with existing toolchains
- Documentation improvements

## License

MIT License - see **[LICENSE](LICENSE)** for details.