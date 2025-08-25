# Contributing to CORE

Thank you for joining CORE’s mission to pioneer self-governing software! Whether you’re fixing a typo or designing AI agents, your contribution helps shape AI-driven development. This guide makes contributing easy for beginners while providing depth for experts.

---

## Our Philosophy: Principled Contributions

CORE is governed by a **“constitution”** (rules in `.intent/`). Contributions must align with principles like `clarity_first`, making the system easier to understand. Start with these docs:

* **README.md**: Project vision and quick demo.
* **Philosophy** (`docs/01_PHILOSOPHY.md`): Mind-Body-Will architecture.
* **Governance** (`docs/03_GOVERNANCE.md`): Safe change process.

**Key Term**: A **“constitutional change”** updates `.intent/` files (e.g., adding a rule), requiring a signed proposal and audit.

---

## Contribution Workflow

1. **Explore Docs & Issues**
   Read README, Roadmap; find/open an issue.

   ↓

2. **Choose Your Contribution**
   Bugs, Docs, Code, or Governance.

   ↓

3. **Submit via GitHub**
   Fork → Branch → Code → Run `make check` → PR.

---

## How to Contribute

### 🏛️ Discuss Architecture & Governance

Shape CORE’s future by discussing its design or rules:

* **Read the Roadmap**: See `docs/04_ROADMAP.md` for challenges (e.g., CognitiveService for AI roles).
* **Propose Changes**: Suggest new principles or policies via GitHub Issues. Example: Add a policy for API rate limiting in `.intent/policies/safety_policies.yaml`.
* **Why It Matters**: Your ideas advance CORE to **A1 autonomy** (auto-PRs).

---

### 🐞 Report Bugs

Strengthen the **ConstitutionalAuditor** by reporting issues:

* **Include**: Command run, full error/traceback, your analysis.
* **Example**: “Auditor missed an import in `src/api/`; here’s the log.”
* **Beginner Task**: Run `make audit` on a test project and report a missed violation.

---

### ✍️ Improve Documentation

Docs drive **clarity\_first**. Help by:

* Fixing typos or unclear sections.
* Adding examples or diagrams (e.g., for audit flow).
* **Beginner Task**: Clarify a sentence in `docs/09_WORKED_EXAMPLE.md`.

---

### 💻 Contribute Code

Code contributions must follow CORE’s governance.

#### 1. Code Conventions

* **Formatting**: Use `black` (`make format`).
* **Linting**: `ruff` enforces quality (`make check`).
* **Type Hints**: Required for all functions/methods.
* **Docstrings**: Every public module/class/function needs one.
* **Capability Tags**: Add `# CAPABILITY: <name>` for key functions.

#### 2. Architecture Rules

* **Domains**: Defined in `.intent/knowledge/source_structure.yaml` (e.g., `core`, `agents`).
* **Imports**: Only use `allowed_imports` from that file. Propose constitutional changes for new imports.
* **Auditor**: Enforces rules via `make check`.

#### 3. Dependencies

* **Use Poetry**: `poetry add <package>` or `poetry add --group dev <package>`.
* **Install**: `poetry install`.
* **Tip**: Run `poetry shell` if commands fail.

#### 4. Testing

* **Write tests** in `tests/` (unit, integration, governance).
* **Goal**: 80%+ coverage (`poetry run pytest --cov`).
* **Run**: `make test`.
* **Beginner Task**: Add a test for `src/system/tools/symbol_processor.py`.

#### 5. Submission Steps

1. Find/open a GitHub Issue.
2. Fork repo, create branch (e.g., `fix/docstring`).
3. Write code/tests, following conventions.
4. Run checks:

   * `make fast-check`: Linting + unit tests.
   * `make check`: Full audit (**required**).
   * `make format`: Fix formatting.
5. Submit PR, linking to the issue.

**Troubleshooting**:

* Audit failure? Check `reports/drift_report.json`.
* Poetry issues? Verify Python 3.12+ and `.env`.

---

## Example Contributions

* **Beginner**: Add a docstring to `src/system/tools/file_scanner.py`.
* **Intermediate**: Write a test for CognitiveService (Roadmap Phase 2).
* **Advanced**: Implement a new starter kit for a CLI app in `src/system/starter_kits/`.

---

## Why Contribute?

Your work helps CORE evolve from **observing codebases (A0)** to **generating apps autonomously (A4)**.
Be part of the future of safe, AI-driven software!

**Quick Start**: Fix a typo in a doc or add a `# CAPABILITY:` tag, then run `make check`.

---

## Questions?

Ask in **GitHub Issues** or join our **community (TBD)**.
We’re excited to collaborate!
