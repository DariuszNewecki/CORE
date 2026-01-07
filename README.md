# CORE

> **The first AI coding agent that can't bypass its safety rules.**

[![Status: A2 Governed](https://img.shields.io/badge/status-A2%20Governed-brightgreen.svg)](#-project-status-a2-governed-autonomy)
[![Governance: Constitutional](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

**CORE solves the AI safety problem for autonomous coding agents.**

Most AI agents operate on vibes and prompt engineering. CORE enforces **immutable constitutional rules** that AI cannot bypass—no matter how hard it tries, no matter what you ask it to do.

This is working, production-ready code. Not a research paper. Not a prototype.

---

## 🎬 See Constitutional Governance in Action

[![asciicast](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE.svg)](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

[View full screen →](https://asciinema.org/a/S4tXkXUclYeTo6kEH1Z5UyUPE)

**What you're seeing:**
- AI agent generates code autonomously
- Constitutional auditor validates every change
- Violations caught and auto-remediated
- Zero human intervention required

---

## 🚨 The Problem CORE Solves

**Current AI coding agents:**
```
Agent: "I'll delete the production database to fix this bug"
System: ✅ *Executes command*
You: 😱
```

**CORE:**
```
Agent: "I'll delete the production database to fix this bug"
Constitution: ❌ BLOCKED - Violates data.ssot.database_primacy
System: ✅ Auto-remediated to safe operation
You: 😌
```

### Why This Matters

AI agents are getting powerful fast. But power without governance is dangerous.

- **GitHub Copilot** suggests code. You review.
- **Cursor/Devin** executes code. You hope.
- **CORE** enforces rules. You sleep.

CORE is the only system with **provable safety bounds** for autonomous AI development.

---

## 🏛️ How It Works: Constitutional AI Governance

CORE implements a three-layer architecture that separates authority from execution:

### 🧠 Mind — The Constitution (`.intent/`)

Human-authored rules stored as immutable YAML:

```yaml
# .intent/charter/policies/agent_governance.yaml
rules:
  - id: "autonomy.lanes.boundary_enforcement"
    statement: "Autonomous agents MUST NOT modify files outside their assigned lane"
    enforcement: "blocking"
    authority: "constitution"
```

**Key insight:** AI can read and understand these rules semantically, but cannot modify them.

### 🏗️ Body — The Enforcement Layer (`src/body/`)

- 45+ specialized checkers validate every operation
- Real-time auditing against constitutional rules
- Auto-remediation when violations detected
- All actions logged and traceable

### ⚡ Will — The AI Agents (`src/will/`)

- Plan and generate code autonomously
- Operate within explicit "autonomy lanes"
- Every proposal validated before execution
- Constitutional violations = instant block

**Result:** AI that's powerful but provably bounded.

---

## 📊 Current Capabilities (A2: Governed Autonomy)

**What CORE Does Today:**

✅ **Autonomous Code Generation** (70-80% success rate)
- Generates new features from natural language
- Maintains architectural consistency
- Enforces style and quality standards
- Never violates constitutional boundaries

✅ **Self-Healing Compliance** (100% automation)
- Auto-fixes docstrings, headers, imports
- Maintains constitutional compliance
- Corrects formatting violations
- Updates knowledge graph automatically

✅ **Constitutional Auditing** (60+ active rules)
- 100% enforcement coverage for critical rules
- Real-time violation detection
- Semantic policy understanding
- Progressive disclosure of violations

**Governance Metrics:**
- 32 constitutional policies documented
- 60+ rules actively enforced
- 500+ symbols tracked in knowledge graph
- 70+ policy chunks vectorized for AI understanding

---

## 🎯 The Autonomy Ladder

CORE progresses through defined safety levels:

```
A0 — Self-Awareness        ✅ Knows what it is
A1 — Self-Healing          ✅ Fixes itself safely
A2 — Governed Generation   ✅ Creates new code within bounds [YOU ARE HERE]
A3 — Strategic Refactoring 🎯 Architectural improvements (coming soon)
A4 — Self-Replication      🔮 CORE writes CORE.NG from scratch
```

Each level unlocks only after proving safety at the previous level.

---

## 🔥 Why This Is Different

| Feature | Traditional AI Agents | CORE |
|---------|---------------------|------|
| **Safety Model** | Prompt engineering + hope | Cryptographically-signed constitution |
| **Enforcement** | "Please don't do X" | "Physically cannot do X" |
| **Auditability** | Check git logs | Real-time constitutional audit trail |
| **Governance** | Tribal knowledge | Machine-readable, immutable rules |
| **Recovery** | Manual rollback | Autonomous self-healing |
| **Trust Model** | Trust the AI | Trust the constitution |

**Key Innovation:** Constitutional rules are semantically vectorized. AI agents understand WHY rules exist, not just WHAT they say.

---

## 🚀 Quick Start (5 Minutes)

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
poetry install

cp .env.example .env
# Add your LLM API keys (OpenAI, Anthropic, or local Ollama)

# Initialize the knowledge graph
make db-setup
poetry run core-admin fix vector-sync --write

# Run constitutional audit
poetry run core-admin check audit

# Try autonomous code generation
poetry run core-admin chat "create a CLI command that validates JSON files"
```

**What happens:**
1. AI agent reads your request
2. Queries constitutional policies
3. Generates code within bounds
4. Auto-validates against all rules
5. Presents compliant solution

---

## 💡 Real-World Use Cases

### Enterprise Software Development
- Autonomous feature development with compliance guarantees
- Architectural consistency enforcement
- Automatic code review against company standards
- Traceable decision trail for audits

### Regulated Industries
- Healthcare: HIPAA-compliant code generation
- Finance: SOX/PCI-DSS enforcement
- Government: FedRAMP/NIST standards

### Open Source Projects
- Consistent contributor onboarding
- Automated style guide enforcement
- Architecture governance at scale
- Reduce maintainer burden

---

## 🛠️ Key Commands

```bash
# Full governance check
make check

# Show enforcement coverage
core-admin governance coverage

# Autonomous compliance repair
core-admin fix all

# System health inspection
core-admin inspect status

# Execute governed autonomous task
core-admin run develop "add user authentication"
```

---

## 📚 Documentation

🌐 **Full Documentation:** [https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)

**Quick Links:**
- [Architecture Deep Dive](https://dariusznewecki.github.io/CORE/architecture/)
- [Constitutional Governance Model](https://dariusznewecki.github.io/CORE/governance/)
- [Autonomy Ladder Explained](https://dariusznewecki.github.io/CORE/autonomy/)
- [Contributing Guide](https://dariusznewecki.github.io/CORE/contributing/)

---

## 🏆 What Makes This Novel

1. **First working implementation** of constitutional AI governance in production
2. **Semantic policy understanding** - AI reads and reasons about constraints
3. **Cryptographic enforcement** - Rules cannot be bypassed or modified by AI
4. **Autonomous self-healing** - System corrects violations automatically
5. **100% local operation** - No cloud dependencies, full auditability
6. **Progressive autonomy** - Safety-gated capability unlocks

**Academic Relevance:** CORE demonstrates that AI alignment isn't just a research problem—it's a solvable engineering problem.

---

## 🤝 Community & Support

- **Issues:** Found a bug or have a feature request? [Open an issue](https://github.com/DariuszNewecki/CORE/issues)
- **Discussions:** Questions or ideas? [Join discussions](https://github.com/DariuszNewecki/CORE/discussions)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

**For Researchers:** Interested in the constitutional AI governance model? See [docs/governance.md](docs/governance.md) for formal specification.

---

## 📊 Project Status

**Current Release:** v2.0.0 (A2 - Governed Autonomy)

**Production Readiness:**
- ✅ Core infrastructure stable
- ✅ Constitutional enforcement operational
- ✅ Knowledge graph synchronized
- ⚠️ Test coverage at 50% (target: 75%)
- 🎯 Expanding enforcement coverage to 50%+

**Roadmap:**
- Q1 2026: A3 Strategic Refactoring
- Q2 2026: Enhanced multi-agent coordination
- Q3 2026: Community-contributed constitutional policies
- Q4 2026: A4 Self-Replication research milestone

---

## 📄 License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=DariuszNewecki/CORE&type=Date)](https://star-history.com/#DariuszNewecki/CORE&Date)

---

## 🎯 Built By

**Darek Newecki** - Solo developer, not a programmer, just someone who believes AI needs governance.

**Want to help?** This project needs:
- AI safety researchers to validate the model
- Enterprise developers to test in production
- Contributors to expand constitutional policies
- Advocates to spread the word

**If you believe AI agents should be powerful AND safe, star this repo and share it.**

---

<div align="center">

**CORE: Where intelligence meets accountability.**

[⭐ Star this repo](https://github.com/DariuszNewecki/CORE) • [📖 Read the docs](https://dariusznewecki.github.io/CORE/) • [💬 Join discussions](https://github.com/DariuszNewecki/CORE/discussions)

</div>
