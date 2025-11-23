# Autonomous Development – What Actually Works Today

> **Status:** This page describes what works **right now** in CORE, and clearly separates **shipped** behaviour from **planned** extensions.

CORE can already take a natural‑language goal, turn it into a governed "crate" of work, and drive it through:

1. **Autonomous code generation**
2. **Validation (formatting, linting, tests)**
3. **Constitutional audits**

All of this is performed under the Mind–Body–Will architecture and enforced by the `.intent/` constitution.

---

## 1. Quick demo (what actually runs)

From your project root:

```bash
# Start your environment
poetry install

# Example: ask CORE to implement a small feature
poetry run core-admin develop feature "Add health endpoint"
```

In the background, CORE will:

1. **Create a crate** describing your request (intent, context, constraints).
2. Use the **Autonomous Developer** pipeline to generate code, tests, and any supporting artifacts.
3. Run the **validation pipeline** (formatters, linters, tests) over the crate outputs.
4. Run **constitutional audits** (Mind) before any change is considered acceptable.

The result is a **governed feature crate** that is either:

* ✅ **Accepted** – passes validation and audits, ready to be integrated, or
* ❌ **Rejected** – captured with findings so you can inspect what failed.

> The exact CLI flags and options are documented in the [CLI Reference](../developer-guide/03-cli-reference.md) and [CLI Workflows](../developer-guide/05-cli-workflows.md).

---

## 2. End‑to‑end pipeline

This is the high‑level autonomous development pipeline as implemented in CORE today.

| Stage                    | Description                                                                                        | Primary components                                                                                                             | Status                           |
| ------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- |
| 1. Intent capture        | You describe the goal in natural language via CLI.                                                 | `core-admin develop` (Typer app under `src/body/cli`), `will/cli_logic/run.py` / `develop.py` wiring                           | **Shipped**                      |
| 2. Crate creation        | The request is turned into a structured crate: metadata, constraints, files to touch, and context. | `src/body/services/crate_creation_service.py`                                                                                  | **Shipped**                      |
| 3. Context building      | Relevant code, docs, and manifest metadata are collected into an LLM‑ready context.                | `src/services/context/builder.py`, `src/services/context/providers/*`                                                          | **Shipped**                      |
| 4. Autonomous coding     | Agents generate or modify code, tests, and docs inside the crate.                                  | `src/features/autonomy/autonomous_developer.py`, `src/will/agents/coder_agent.py`, `src/will/orchestration/prompt_pipeline.py` | **Shipped**                      |
| 5. Local validation      | Code is formatted, linted, and tests are executed against the crate outputs.                       | `src/services/validation/*` (Black, Ruff, syntax, pytest runner)                                                               | **Shipped**                      |
| 6. Constitutional audits | Mind runs policy and safety checks over the proposed changes.                                      | `src/mind/governance/*`, especially `audit_context.py`, `auditor.py`, `checks/*`                                               | **Shipped**                      |
| 7. Decision & feedback   | Crate is marked as accepted or rejected; findings are recorded for inspection.                     | `src/body/services/crate_processing_service.py`, governance services                                                           | **Shipped (manual integration)** |

The key point: **every autonomous change is validated and audited before you ever merge it**.

---

## 3. What is shipped vs planned

Some parts of the original design are still aspirational. This section makes that explicit.

### 3.1. Shipped today

These pieces exist in `src/` and are used by the CLI:

* **Autonomous Developer core**

  * `src/features/autonomy/autonomous_developer.py`
  * `src/will/agents/coder_agent.py`
  * `src/will/orchestration/cognitive_service.py`
  * `src/will/orchestration/prompt_pipeline.py`
  * `src/will/orchestration/validation_pipeline.py`

* **Crate lifecycle (without long‑running daemon)**

  * `src/body/services/crate_creation_service.py`
  * `src/body/services/crate_processing_service.py`

* **Self‑healing & coverage tooling**

  * `src/features/self_healing/*` – coverage analyzers, test generators, remediation services.
  * `src/mind/governance/checks/*` – coverage, style, ID hygiene, knowledge, security checks.

* **Validation tools**

  * `src/services/validation/black_formatter.py`
  * `src/services/validation/ruff_linter.py`
  * `src/services/validation/test_runner.py`
  * plus syntax and YAML validators.

### 3.2. Planned / not yet implemented

These are described in the vision and planning docs, but **do not yet exist** as working commands or services in `src/`:

* **Crate daemon**

  * Background worker that continuously picks up crates and processes them.
  * CLI group like `core-admin daemon ...` and corresponding systemd unit.

* **Rich crate management CLI**

  * Commands such as `core-admin crate status`, `crate list`, `crate show`, `crate retry`.
  * A structured namespace for inspecting, filtering, and replaying crates.

* **Debt scanner & auto‑refactorer**

  * Commands such as `core-admin develop scan` for automated technical debt surveys.
  * Dedicated refactorer services beyond the current self‑healing and coverage tooling.

* **Peer review CLI group**

  * Commands like `core-admin review export` / `review constitution` to assist human reviewers.

Whenever you see these in the docs, treat them as **Phase 2+** capabilities rather than currently‑shipped behaviour.

---

## 4. How this maps to Mind–Body–Will

Autonomous development is not a separate subsystem; it is the coordinated use of Mind, Body, and Will.

* **Mind (`src/mind/`)**

  * Defines and enforces the rules: policies, checks, auditors, constitutional gates.
  * Validates that any autonomous change is safe, compliant, and within scope.

* **Body (`src/body/`, `src/features/`, `src/services/`)**

  * Executes the work: crate services, validation tools, persistence, context builders.
  * Exposes CLI commands via `core-admin` (Typer apps in `src/body/cli`).

* **Will (`src/will/`)**

  * Hosts the agents and orchestration glue that actually *decide* what to generate.
  * Uses LLMs (via `src/services/llm/*`) under the constraints provided by Mind.

When you run `core-admin develop feature ...`, you are effectively triggering a **Mind‑governed Will acting through Body**.

---

## 5. Current limitations

To keep expectations realistic, here are the most important current limitations:

1. **No always‑on daemon yet**
   Crates are processed when you invoke CLI commands; there is no long‑running daemon that automatically drains crate queues.

2. **Manual integration step**
   CORE can prepare governed crates; you still decide when and how to merge them into your main branch or deployment pipeline.

3. **Limited refactor automation**
   Self‑healing and refactoring capabilities exist, but the full "debt scanner" vision is not yet implemented as a single `develop scan` command.

4. **Some CLI docs describe future commands**
   If a command referenced in the docs is missing from `core-admin --help`, consider it planned rather than a bug.

---

## 6. How to think about autonomous development in CORE

CORE is deliberately conservative:

* **Autonomy is always governed** – Mind (policies, audits, constitution) can veto any generated change.
* **Crates are the unit of work** – everything autonomous happens inside a crate with clear boundaries.
* **Self‑healing is first‑class** – coverage, style, IDs, and knowledge alignment are treated as autonomous tasks, not chores.

When you extend CORE (new features, new agents, new policies), treat this page as the contract:

* If something is described as **shipped**, keep the implementation in sync.
* If you add a new autonomous capability, add it to the pipeline and explicitly mark its status here.

That way, this document remains a truthful, high‑signal description of what CORE can *actually* do today.
