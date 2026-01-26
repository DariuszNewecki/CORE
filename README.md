# CORE

> **The first AI coding agent with a universal operating system for autonomous operations.**

[![Status: A2+ Universal Workflow](https://img.shields.io/badge/status-A2%2B%20Universal%20Workflow-brightgreen.svg)](#-project-status)
[![Governance: Constitutional](https://img.shields.io/badge/governance-Constitutional-blue.svg)](#-constitutional-governance)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://dariusznewecki.github.io/CORE/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![codecov](https://codecov.io/gh/DariuszNewecki/CORE/graph/badge.svg)](https://codecov.io/gh/DariuszNewecki/CORE)

**CORE solves two problems:**
1. **AI safety:** Immutable constitutional rules that AI cannot bypass
2. **Autonomous operations:** Universal workflow pattern that closes all loops

Most AI agents operate on vibes and prompt engineering. CORE enforces **constitutional governance** through a **universal orchestration model** that makes every operation self-correcting, traceable, and composable.

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

### Problem 1: AI Without Guardrails

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

### Problem 2: Ad-Hoc Workflows

**Current approach:**
```python
# Each command implements its own retry logic
def fix_clarity(file):
    for attempt in range(3):  # Magic number
        result = llm.refactor(file)
        if looks_good(result):  # Unclear criteria
            break
    save(result)  # No validation
```

**CORE's Universal Workflow:**
```python
# Every operation follows the same pattern
INTERPRET → ANALYZE → STRATEGIZE → GENERATE → EVALUATE → DECIDE

# Self-correction is universal, not command-specific
if not evaluator.solved():
    if strategist.should_pivot():
        strategy = strategist.adapt(failure_pattern)
    continue_loop()
```

---

## 🎯 What's New in 2.2.0: The Operating System

**CORE now has a universal orchestration model** that composes all autonomous operations.

### The Universal Workflow Pattern

Every autonomous operation—from simple file fixes to full feature development—follows this pattern:

```
┌─────────────────────────────────────────┐
│ INTERPRET: What does the user want?    │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ ANALYZE: What are the facts?           │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ STRATEGIZE: What approach to use?      │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ GENERATE: Create solution               │
└────────────────┬────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│ EVALUATE: Is it good enough?           │
└────────────────┬────────────────────────┘
                 ↓
         ┌──────────────┐
         │   SOLVED?    │
         └──────┬───────┘
                │
        ┌───────┴────────┐
        │ YES            │ NO
        ↓                ↓
    TERMINATE    Continue trying?
                        │
                 ┌──────┴──────┐
                 │ YES         │ NO
                 ↓             ↓
          (adapt & retry)  TERMINATE
```

### Why This Matters

**Before 2.2.0:** Collection of autonomous capabilities with ad-hoc orchestration
**After 2.2.0:** Universal pattern that closes all loops

**What "closes all loops" means:**
- Every operation can self-correct (not just some)
- Every decision is traceable (not just logged)
- Every failure triggers adaptation (not just retry)
- Every component is composable (not just callable)

**Result:** CORE becomes an **operating system for AI-driven development**, not just a collection of tools.

---

## 🏛️ How It Works: Constitutional AI Governance + Universal Orchestration

CORE implements a three-layer architecture with universal workflow orchestration:

### 🧠 Mind — The Constitution (`.intent/`)

Human-authored rules stored as immutable YAML:

```yaml
# .intent/charter/policies/agent_governance.yaml
rules:
  - id: "autonomy.lanes.boundary_enforcement"
    statement: "Autonomous agents MUST NOT modify files outside their assigned lane"
    enforcement: "blocking"
    authority: "constitution"
    phase: "runtime"  # One of: interpret, parse, load, audit, runtime, execution
```

**New in 2.2.0:** Rules explicitly declare which workflow phase they govern.

### 🏗️ Body — The Execution Layer (`src/body/`)

**Components organized by workflow phase:**

- **Analyzers** (PARSE phase): Extract facts without decisions
  - `FileAnalyzer`: Classify file types and complexity
  - `SymbolExtractor`: Find testable functions and classes

- **Evaluators** (AUDIT phase): Assess quality and identify patterns
  - `FailureEvaluator`: Test failure pattern recognition
  - `ClarityEvaluator`: Cyclomatic complexity measurement

- **Atomic Actions** (EXECUTION phase): Primitive operations
  - `action_edit_file`: Governed file mutations
  - `action_fix_format`: Code formatting
  - 10+ more actions

**Result:** Components are reusable building blocks, not one-off functions.

### ⚡ Will — The AI Orchestration (`src/will/`)

**Strategists make deterministic decisions:**

```python
class TestStrategist(Component):
    """Decides test generation strategy based on file type and failure patterns."""

    async def execute(self, file_type: str, failure_pattern: str = None):
        if failure_pattern == "type_introspection" and count >= 2:
            # Adaptive pivot based on observed pattern
            return "integration_tests_no_introspection"
        elif file_type == "sqlalchemy_model":
            return "integration_tests"
        else:
            return "unit_tests"
```

**Orchestrators compose components:**

```python
class AdaptiveTestGenerator(Orchestrator):
    """Test generation with failure recovery (70-80% success)."""

    async def generate_tests_for_file(self, file_path: str):
        # ANALYZE
        analysis = await FileAnalyzer().execute(file_path)

        # STRATEGIZE
        strategy = await TestStrategist().execute(
            file_type=analysis.data["file_type"]
        )

        # GENERATE → EVALUATE → DECIDE (adaptive loop)
        for attempt in range(max_attempts):
            code = await generate(strategy)
            evaluation = await FailureEvaluator().execute(code)

            if evaluation.data["solved"]:
                return code  # Success!

            if evaluation.data["should_pivot"]:
                strategy = await strategist.adapt(evaluation.data["pattern"])
```

**Result:** Every workflow is self-correcting by design.

---

## 📊 Current Capabilities

### ✅ Autonomous Code Generation (A2)
- Generates new features from natural language (70-80% success)
- Maintains architectural consistency
- Enforces style and quality standards
- **New:** Adaptive strategy pivots based on failure patterns

### ✅ Self-Healing Compliance (A1)
- Auto-fixes docstrings, headers, imports (100% automation)
- Maintains constitutional compliance
- Corrects formatting violations
- **New:** Uses universal workflow for all fixes

### ✅ Constitutional Auditing
- 60+ rules actively enforced
- Real-time violation detection
- Semantic policy understanding
- **New:** Phase-aware rule evaluation

### 🎯 Two Interfaces

**`core` CLI** (Conversational):
```bash
$ core "refactor UserService for clarity"
> Analyzing UserService structure...
> Strategy: structural_decomposition
> Generating refactored code...
> Evaluation: 23% complexity reduction
> Apply changes? [y/n]
```
*Status: Foundation exists, workflow integration in progress*

**`core-admin` CLI** (Developer Tools):
```bash
$ core-admin fix clarity src/services/user.py --write
$ core-admin check audit
$ core-admin coverage generate-adaptive src/models/user.py --write
```
*Status: Stable, pattern compliance migration ongoing*

---

## 🏗️ Component Architecture (New in 2.2.0)

**12 Component Categories** mapped to workflow phases:

| Category | Phase | Count | Purpose |
|----------|-------|-------|---------|
| **Interpreters** | INTERPRET | 1/3 ✅ | Parse intent → task structure |
| **Analyzers** | PARSE | 2/5 | Extract facts |
| **Providers** | LOAD | 3 | Data source adapters |
| **Evaluators** | AUDIT | 2/5 | Assess quality |
| **Strategists** | RUNTIME | 2/5 | Make decisions |
| **Orchestrators** | RUNTIME | 5 | Compose workflows |
| **Atomic Actions** | EXECUTION | 10+ | Primitive operations |

**Total: 40+ components** organized by constitutional phase.

**What this enables:**
- **Reusability**: Same analyzer in multiple workflows
- **Composability**: Mix and match components
- **Testability**: Test components independently
- **Traceability**: Every decision logged by phase

---

## 🎯 The Autonomy Ladder

CORE progresses through defined safety levels:

```
A0 — Self-Awareness        ✅ Knows what it is
A1 — Self-Healing          ✅ Fixes itself safely
A2 — Governed Generation   ✅ Creates new code within bounds
A2+ — Universal Workflow   ✅ All operations self-correcting [YOU ARE HERE]
A3 — Strategic Refactoring 🎯 Architectural improvements (roadmap defined)
A4 — Self-Replication      🔮 CORE writes CORE.NG from scratch
```

**New in 2.2.0:** A2+ represents having the **architectural foundation** for A3 and beyond.

---

## 🔥 Why This Is Different

| Feature | Traditional AI Agents | CORE |
|---------|---------------------|------|
| **Safety Model** | Prompt engineering + hope | Cryptographically-signed constitution |
| **Enforcement** | "Please don't do X" | "Physically cannot do X" |
| **Self-Correction** | Manual retry logic per command | Universal adaptive loops |
| **Composability** | Copy-paste code between tools | Reusable component library |
| **Auditability** | Check git logs | Phase-aware constitutional audit trail |
| **Governance** | Tribal knowledge | Machine-readable, immutable rules |
| **Architecture** | Ad-hoc orchestration | Universal workflow pattern |
| **Trust Model** | Trust the AI | Trust the constitution + workflow |

**Key Innovation #1:** Constitutional rules are semantically vectorized. AI agents understand WHY rules exist, not just WHAT they say.

**Key Innovation #2:** Universal workflow pattern makes self-correction a system property, not a feature.

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

# Try adaptive test generation (uses universal workflow)
poetry run core-admin coverage generate-adaptive src/models/user.py --write

# Try conversational interface (in progress)
poetry run core "analyze the FileAnalyzer component"
```

---

## 💡 Real-World Use Cases

### Enterprise Software Development
- Autonomous feature development with compliance guarantees
- Architectural consistency enforcement via strategists
- Automatic code review against company standards
- Traceable decision trail for audits
- **New:** Self-correcting CI/CD pipelines

### Regulated Industries
- Healthcare: HIPAA-compliant code generation
- Finance: SOX/PCI-DSS enforcement through constitutional rules
- Government: FedRAMP/NIST standards as policies
- **New:** Audit trails show decision reasoning, not just outcomes

### Open Source Projects
- Consistent contributor onboarding
- Automated style guide enforcement
- Architecture governance at scale via strategists
- Reduce maintainer burden through self-healing
- **New:** Contributors can add evaluators/strategists, not just code

---

## 🛠️ Key Commands

```bash
# Governance & Audit
make check                              # Full constitutional audit
core-admin governance coverage          # Show enforcement coverage
core-admin check audit                  # Run audit with detailed output

# Autonomous Operations (Universal Workflow)
core-admin coverage generate-adaptive FILE --write  # Test gen with adaptation
core-admin fix clarity FILE --write                 # Refactor for clarity
core-admin develop "add user auth"                  # Full feature development

# Developer Tools
core-admin fix all                      # Fix all compliance issues
core-admin inspect status               # System health check
core-admin knowledge sync               # Update knowledge graph
```

---

## 📚 Documentation

🌐 **Full Documentation:** [https://dariusznewecki.github.io/CORE/](https://dariusznewecki.github.io/CORE/)

**Quick Links:**
- [Architecture Deep Dive](https://dariusznewecki.github.io/CORE/architecture/)
- [Constitutional Governance Model](https://dariusznewecki.github.io/CORE/governance/)
- [**NEW:** Universal Workflow Pattern](https://dariusznewecki.github.io/CORE/workflow-pattern/) — The operating system
- [Component Library Reference](https://dariusznewecki.github.io/CORE/components/)
- [Autonomy Ladder Explained](https://dariusznewecki.github.io/CORE/autonomy/)
- [Contributing Guide](https://dariusznewecki.github.io/CORE/contributing/)

---

## 🏆 What Makes This Novel

1. **First working implementation** of constitutional AI governance in production
2. **Universal workflow pattern** that closes all loops for autonomous operations
3. **Semantic policy understanding** - AI reads and reasons about constraints
4. **Cryptographic enforcement** - Rules cannot be bypassed or modified by AI
5. **Component architecture** - 40+ reusable building blocks organized by phase
6. **Autonomous self-healing** - System corrects violations automatically
7. **100% local operation** - No cloud dependencies, full auditability
8. **Progressive autonomy** - Safety-gated capability unlocks

**Academic Relevance:** CORE demonstrates that:
- AI alignment isn't just a research problem—it's a solvable engineering problem
- Universal orchestration patterns enable reliable autonomous systems
- Constitutional governance can be both strict AND flexible

---

## 📊 Project Status

**Current Release:** v2.2.0 (2026-01-08) — Universal Workflow Pattern

**What's Stable:**
- ✅ Constitutional governance operational (60+ rules enforced)
- ✅ Component library established (40+ components)
- ✅ Universal workflow pattern documented
- ✅ Adaptive test generation working (70-80% success)
- ✅ Self-healing compliance (100% automation)

**What's In Progress:**
- 🔄 Pattern compliance migration (~12% complete)
- 🔄 RequestInterpreter implementation (unblocks conversational interface)
- 🔄 Missing strategists/evaluators (3 of each needed)
- 🔄 Command migration to universal workflow

**Roadmap:**
- **Q1 2026**: Complete pattern migration, full `core` CLI autonomy
- **Q2 2026**: A3 Strategic Refactoring with universal workflow
- **Q3 2026**: Web/API interfaces (natural evolution)
- **Q4 2026**: A4 Self-Replication research milestone

**For Transparency:**
- Test coverage: 14% (target: 75%)
- Enforcement coverage: Varies by policy domain
- Component gap: 9 critical components needed
- Legacy code: Being incrementally migrated

---

## 🤝 Community & Support

- **Issues:** Found a bug or have a feature request? [Open an issue](https://github.com/DariuszNewecki/CORE/issues)
- **Discussions:** Questions or ideas? [Join discussions](https://github.com/DariuszNewecki/CORE/discussions)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

**For Researchers:**
- Constitutional AI governance: See [docs/governance.md](docs/governance.md)
- Universal workflow pattern: See `.intent/papers/CORE-Adaptive-Workflow-Pattern.md`

**For Developers:**
- Want to build a component? See [docs/components.md](docs/components.md)
- Want to add a strategist? See [docs/strategists.md](docs/strategists.md)

---

## 📄 License

Licensed under the **MIT License**. See [LICENSE](LICENSE).

---

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=DariuszNewecki/CORE&type=Date)](https://star-history.com/#DariuszNewecki/CORE&Date)

---

## 🎯 Built By

**Darek Newecki** - Solo developer, not a programmer, just someone who believes AI needs **both** power **and** governance.

**Want to help?** This project needs:
- AI safety researchers to validate the constitutional model
- AI orchestration experts to improve the workflow pattern
- Enterprise developers to test in production
- Component contributors (analyzers, evaluators, strategists)
- Advocates to spread the word

**If you believe AI agents should be powerful AND safe AND composable, star this repo and share it.**

---

<div align="center">

**CORE: Where intelligence meets accountability meets orchestration.**

[⭐ Star this repo](https://github.com/DariuszNewecki/CORE) • [📖 Read the docs](https://dariusznewecki.github.io/CORE/) • [💬 Join discussions](https://github.com/DariuszNewecki/CORE/discussions)

</div>
