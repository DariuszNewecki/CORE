# CORE — The Self‑Improving System Architect

> **Where Intelligence Lives.**

[![Status: A2 Achieved](https://img.shields.io/badge/status-A2%20Achieved-brightgreen.svg)](#-project-status)
[![Constitutional Governance](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

CORE is a **self‑governing, constitutionally aligned AI development system** capable of planning, writing, validating, and evolving software **autonomously and safely**. It is designed for environments where **trust, traceability, and governance matter as much as raw capability**.

Built on **industry-standard governance patterns** (Kubernetes, AWS, OPA), CORE demonstrates how AI agents can operate with **bounded autonomy** - powerful yet provably constrained by human-defined constitutional principles.

## See It In Action

[![asciicast](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.svg)](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

[View full screen →](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

---

## 🏛️ Project Status: A2 Autonomy Achieved

**CORE has achieved Level 2 Autonomy (A2): Autonomous Code Generation**

### Current Capabilities

* ✅ **A0 (Self-Awareness)**: 513 symbols vectorized, 66 module anchors, knowledge graph operational
* ✅ **A1 (Self-Healing)**: Automatic docstrings, headers, imports, formatting, constitutional compliance
* ✅ **A2 (Code Generation)**: 70-80% success rate on autonomous code generation with constitutional governance
* 🎯 **A3 (Strategic Refactoring)**: Next frontier - multi-file architectural improvements

### Live Metrics (v2.0.0)

**Constitutional Governance:**
* 32 constitutional policies documented
* 60+ rules actively enforced (40.5% enforcement coverage, targeting 50%+)
* 100% enforcement: agent_governance, dependency_injection, code_execution
* Auto-regenerating coverage reports (Big Boys pattern: kubectl, git, docker)

**Autonomous Capabilities:**
* **Code Generation Success Rate**: 70-80% (up from 0%)
* **Semantic Placement Accuracy**: 100% (up from 45%)
* **Knowledge Graph**: 513 symbols, 66 module anchors, 73 policy chunks vectorized
* **Test Coverage**: 48-51% (constitutional requirement: 75%)

**Recent Achievements (v2.0 Migration):**
* ✅ **Constitutional Modernization**: Migrated to industry-standard flat rules structure
* ✅ **Complete Documentation**: 4 constitutional standards following Kubernetes patterns
* ✅ **Progressive Disclosure UX**: Coverage reports show gaps first, not overwhelming detail
* ✅ **Parser Robustness**: Auto-discovery of rules, never breaks with new categories
* ✅ **Backward Compatible**: Supports both v1 (nested) and v2 (flat) formats during transition

---

## 🧠 What Is CORE?

Traditional systems drift: architecture diverges from implementation; design documents rot; no one has the full picture.

CORE fixes this by making **the architecture machine‑readable and enforceable**.

It is built on the **Mind–Body–Will** model:

### 🧠 Mind — The Constitution & State (`.intent/`, PostgreSQL)

* The **Constitution** defines immutable laws: structure, policies, schemas, allowed dependencies.
* The **Database** stores every symbol, capability, and relation as the **Single Source of Truth**.
* **Semantic Infrastructure**: Policies, symbols, and architectural context vectorized for AI reasoning.
* **Governance Framework**: Industry-aligned (Kubernetes/AWS/OPA) constitutional governance.

### 🏗️ Body — The Machinery (`src/body/`, `src/services/`)

* Provides deterministic tools: auditing, filesystem operations, code parsing, git control.
* A centralized **Service Registry** ensures clean lifecycle management and singleton resources.
* **Constitutional Auditor** enforces governance rules and tracks violations.
* **45 specialized checkers** validate compliance across the codebase.

### ⚡ Will — The Reasoning Layer (`src/will/`)

* AI Agents that plan, write, and review code autonomously.
* Agents never act freely: **every action is pre‑validated** against the Constitution.
* **Context-Aware Code Generation**: Rich semantic context enables accurate, policy-compliant code.
* **Bounded Autonomy**: Agents operate in defined "autonomy lanes" with explicit permissions.

This creates a system that can **understand itself**, detect deviations, and evolve safely.

---

## 🏛️ Governance Architecture

CORE implements a **two-paradigm governance system** following industry best practices:

```
┌─────────────────────────────────────────────────────────────┐
│              CONSTITUTIONAL LAYER                           │
│        (Principles - System-Level Governance)               │
│                                                             │
│  authority.yaml          → Who decides what                 │
│  boundaries.yaml         → What's immutable                 │
│  risk_classification.yaml → What needs oversight            │
│                                                             │
│  Paradigm: Foundational, coarse-grained, very stable       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  POLICY LAYER                               │
│           (Rules - Code-Level Enforcement)                  │
│                                                             │
│  code_standards.yaml     → 17/31 enforced (54%) 🆕          │
│  logging_standards.yaml  → Ready to migrate                 │
│  data_governance.yaml    → Ready to migrate                 │
│  agent_governance.yaml   → 5/5 enforced (100%) ✅           │
│                                                             │
│  Paradigm: Implementation-specific, fine-grained, dynamic   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              ENFORCEMENT LAYER                              │
│        (Checkers - Continuous Verification)                 │
│                                                             │
│  45 checkers × 60+ rules = 40.5% coverage                  │
│  Auto-discovery via flat rules array                        │
│  Progressive disclosure UX (like kubectl/git/docker)        │
└─────────────────────────────────────────────────────────────┘
```

### Two Governance Paradigms

**Principles (Constitutional - System Level)**
* Foundational invariants (authority, boundaries, risk)
* Coarse-grained, very stable
* Example: *"The database is the single source of truth"*
* Defined in: `authority.yaml`, `boundaries.yaml`, `risk_classification.yaml`

**Rules (Policies - Code Level)**
* Implementation requirements (code quality, operations)
* Fine-grained, more dynamic
* Example: *"All code MUST pass ruff linting"*
* Defined in: `code_standards.yaml`, `logging_standards.yaml`, etc.

**Relationship**: Principles set boundaries → Policies implement boundaries → Checkers verify compliance

---

## 📚 Constitutional Documentation

CORE provides **complete governance documentation** following industry standards (Kubernetes, AWS, OPA):

| Document | Purpose | Status |
|----------|---------|--------|
| **[GLOBAL-DOCUMENT-META-SCHEMA](/.intent/charter/constitution/GLOBAL-DOCUMENT-META-SCHEMA.yaml)** | Universal header requirements for all .intent documents | ✅ Active |
| **[CONSTITUTION-STRUCTURE](/.intent/charter/constitution/CONSTITUTION-STRUCTURE.yaml)** | Principles-based system governance (authority, boundaries, risk) | 🆕 v2.0 |
| **[RULES-STRUCTURE](/.intent/charter/constitution/RULES-STRUCTURE.yaml)** | Universal standard for enforceable rules (flat array pattern) | 🆕 v2.0 |
| **[POLICY-STRUCTURE](/.intent/charter/constitution/POLICY-STRUCTURE.yaml)** | Code quality and operational policies | 🆕 v2.0 |
| **[PATTERN-STRUCTURE](/.intent/charter/constitution/PATTERN-STRUCTURE.yaml)** | Architectural and behavioral patterns | 🆕 v2.0 |

**Key Innovation**: Flat rules array pattern (not nested sections)
* ✅ Parser-friendly - never breaks when new categories added
* ✅ Industry-aligned - matches Kubernetes, AWS IAM, OPA/Rego
* ✅ Extensible - add categories without code changes
* ✅ Self-documenting - categories visible in each rule

---

## 🔒 Constitutional Governance (Industry-Aligned)

CORE's governance system implements **bounded AI autonomy** through constitutional constraints:

### Core Principles

1. **Human Authority**: Critical operations require human approval
2. **Immutable Boundaries**: Constitution cannot be modified by AI agents
3. **Continuous Audit**: All operations validated against governance rules
4. **Semantic Understanding**: AI agents reason about their own constraints
5. **Progressive Disclosure**: Show actionable info, not overwhelming detail

### Governance in Action

**Check enforcement coverage:**
```bash
core-admin governance coverage --format hierarchical
```

**Output shows:**
- Top gaps per policy (actionable)
- Category breakdown (scannable)
- Migration progress (v1 → v2 flat structure)
- Links to full details (progressive disclosure)

**Example output:**
```
### ⚠️ code_standards.yaml 🆕
**Enforcement**: 17/31 rules (54%)
**Format**: New (flat rules array) ✨

**Top gaps** (highest priority):
- ❌ `code.python_module_naming` (error) - snake_case enforcement
- ❌ `code.python_test_module_naming` (error) - test_ prefix
- ❌ `header_compliance` (error) - file headers

**Enforcement by category**:
- capabilities: 4/4 rules (100%) ✅
- style: 3/7 rules (43%)
- naming: 1/10 rules (10%)

📋 Full rule list: `core-admin governance coverage --policy code_standards`
```

### Enforcement Architecture

**Constitutional Layer** (ValidatorService, IntentGuard)
- Pre-execution validation against principles
- Runtime protection of boundaries
- Risk tier assessment

**Policy Layer** (Auditor + 45 Checkers)
- Post-commit compliance verification
- Coverage tracking and reporting
- Auto-remediation for simple violations

**Result**: AI agents that are powerful yet provably bounded by human-defined constraints.

---

## 🎯 The Autonomy Ladder

CORE progresses through defined autonomy levels:

```
A0: Self-Awareness          ✅ Knowledge graph, symbol vectorization
A1: Self-Healing            ✅ Autonomous fixes for drift, formatting, compliance
A2: Code Generation         ✅ Create new features with constitutional governance
A3: Strategic Refactoring   🎯 Multi-file architectural improvements
A4: Self-Replication        🔮 Write CORE.NG from scratch based on functionality
```

**Current Focus**: Reaching 50%+ enforcement coverage and A3 capabilities

---

## 🎓 Academic Contribution

CORE demonstrates **practical constitutional AI governance** at scale:

* ✅ **Working implementation** of bounded AI autonomy (not theoretical)
* ✅ **Industry-aligned patterns** (Kubernetes, AWS, OPA) applied to AI safety
* ✅ **Semantic policy understanding** - AI agents reason about their own constraints
* ✅ **Verifiable compliance** - continuous audit with coverage metrics
* ✅ **Open source** - reproducible research for AI safety community
* ✅ **Production-grade** - 60,000+ lines, 513 symbols, 32 policies

**Suitable for presentation at**:
- AI Safety conferences (demonstrating bounded autonomy)
- Software Engineering research (constitutional software patterns)
- Autonomous Systems symposia (self-governing systems)

**Key Research Questions Addressed**:
1. Can AI agents operate safely within constitutional bounds?
2. How do we make governance rules machine-understandable?
3. What enforcement coverage is needed for safe autonomy?

---

## 🚀 Getting Started (5‑Minute Demo)

Run a minimal walkthrough: create an API, break a rule, and watch CORE catch it.

👉 **[Run the Worked Example](docs/09_WORKED_EXAMPLE.md)**

---

## 📖 Documentation Portal

🌐 **[https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)**

* **What is CORE?** – Foundations & philosophy
* **Architecture** – Mind/Body/Will, Service Registry, Knowledge Graph
* **Governance** – Constitutional framework and enforcement
* **Autonomy Ladder** – From self-awareness to self-replication
* **Roadmap** – Towards A3, A4, and full autonomous delivery
* **Contributing** – How to collaborate

---

## ⚙️ Installation & Quick Start

**Requirements:** Python 3.12+, Poetry, PostgreSQL, Qdrant (optional)

```bash
# Clone and install
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

# Prepare config
cp .env.example .env
# Add LLM keys (OpenAI, Anthropic, Ollama)

# 1. Initialize databases
make db-setup

# 2. Build Knowledge Graph
poetry run core-admin fix vector-sync --write

# 3. Run full constitutional audit
poetry run core-admin check audit

# 4. Check governance coverage
poetry run core-admin governance coverage --format hierarchical

# 5. Try autonomous code generation
poetry run core-admin chat "create a CLI command that validates JSON files"
```

---

## 🛠️ Common Commands

| Command                                | Description                                      |
| -------------------------------------- | ------------------------------------------------ |
| `make check`                           | Run Lint, Test, Audit (full governance pipeline) |
| `core-admin fix all`                   | Autonomous repair: headers, metadata, formatting |
| `core-admin governance coverage`       | Show enforcement coverage (progressive disclosure)|
| `core-admin check audit`               | Run constitutional compliance audit              |
| `core-admin inspect status`            | Check DB, migrations, and registry health        |
| `core-admin run develop`               | Execute autonomous, governed coding task         |

---

## 📊 Success Metrics

From initial implementation to A2 achievement:

| Metric | Initial | Current | Target |
|--------|---------|---------|--------|
| Code generation success | 0% | **70-80%** | 90%+ |
| Semantic placement accuracy | 45% | **100%** | 100% |
| Test generation success | 0% | **70-80%** | 90%+ |
| Knowledge graph symbols | 0 | **513** | 1000+ |
| Policy chunks vectorized | 0 | **73** | 100+ |
| Enforcement coverage | - | **40.5%** | **50%+** |
| Policies at 100% enforcement | 0 | **3** | **10+** |

All improvements driven by constitutional governance and semantic infrastructure.

---

## 🗺️ Roadmap

### Short-term (Q1 2026)
- 🎯 Reach 50%+ enforcement coverage
- 🎯 Migrate remaining policies to v2.0 flat structure
- 🎯 Achieve A3: Strategic multi-file refactoring
- 🎯 Present to AI safety research community

### Medium-term (Q2-Q3 2026)
- 🔮 75% enforcement coverage (constitutional requirement)
- 🔮 Self-healing test generation
- 🔮 Autonomous architectural improvements
- 🔮 Academic paper on constitutional AI governance

### Long-term (Q4 2026+)
- 🌟 A4: Self-replication (CORE writes CORE.NG)
- 🌟 Full autonomous feature delivery
- 🌟 Industry adoption of constitutional patterns
- 🌟 Open-source AI safety toolkit

---

## 🤝 Contributing

CORE welcomes contributions! Areas of particular interest:

1. **New Constitutional Checkers**: Increase enforcement coverage
2. **Policy Migration**: Help migrate remaining policies to v2.0 flat structure
3. **Documentation**: Improve guides, examples, worked demonstrations
4. **Research**: Academic collaboration on constitutional AI governance
5. **Testing**: Expand test coverage toward 75% constitutional requirement

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for guidelines.

---

## 📄 License

Licensed under the **MIT License**. See `LICENSE`.

---

## 🙏 Acknowledgments

CORE builds on ideas from:
- **Constitutional AI** (Anthropic) - AI alignment through principles
- **Kubernetes** - Governance patterns and API conventions
- **AWS IAM** - Policy structure and enforcement
- **OPA/Rego** - Declarative policy language

Special thanks to the AI safety research community for foundational work on bounded autonomy.

---

**Built with ❤️ by developers who believe AI should be powerful AND safe.**

*"The best way to predict the future is to build it — constitutionally."*
