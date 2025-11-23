# CORE Developer Cheat Sheet

This cheat sheet provides a **fast, accurate reference** for daily development inside CORE.
It reflects the **real system as it exists today** and follows the Mind–Body–Will architecture.

If you need a mental model for how CORE works in less than 5 minutes, this is it.

---

# 🔷 1. Architecture at a Glance

```
src/
├── api/            # HTTP API surface
├── body/           # CLI, actions, crate services
├── features/       # autonomy, introspection, self-healing, maintenance
├── mind/           # governance, policies, auditor, checks
├── services/       # DB, LLMs, validation, context, storage
├── shared/         # utilities, config, common models
└── will/           # agents, orchestration, reasoning
```

### 🔸 Mind — Governance (`src/mind/` + `.intent/`)

Defines rules, policies, audits, domain boundaries.

### 🔸 Body — Execution (`src/body/`, `src/features/`, `src/services/`)

Runs CLI operations, validation, crate lifecycle, knowledge syncing.

### 🔸 Will — Agents (`src/will/`)

Reasoning, planning, coding, reviewing. Always governed.

---

# 🔷 2. Daily Commands

### **Audit Everything**

```bash
poetry run core-admin check audit
```

Runs the full Constitutional Auditor.

### **Fix Metadata/IDs**

```bash
poetry run core-admin fix ids --write
poetry run core-admin fix metadata --write   # If applicable
```

### **Sync Knowledge Graph**

```bash
poetry run core-admin manage database sync-knowledge
```

### **Format & Lint Automatically**

```bash
poetry run core-admin fix code-style --write
```

---

# 🔷 3. Autonomous Development (A1)

### **Ask CORE to build a feature**

```bash
poetry run core-admin develop feature "Add health endpoint"
```

CORE will:

1. Create a crate
2. Build context
3. Generate code/tests
4. Validate output
5. Run constitutional audits
6. Accept/reject the crate

**You manually integrate accepted crates.**

---

# 🔷 4. Crate Lifecycle (What Actually Exists Today)

### **Create a crate through autonomous development**

Handled automatically by:

* `crate_creation_service.py`
* `autonomous_developer.py`

### **Process a crate**

```bash
poetry run core-admin run process-crate <crate_id>
```

*(If your CLI includes this command — otherwise crates are processed inline.)*

### **Inspect crates (manual inspection)**

Look inside:

```
.core/crates/
```

for metadata, generated files, validation outputs.

There is **no daemon** and **no crate management CLI** beyond what exists in your `core-admin` tree.

---

# 🔷 5. Validation Pipeline

CORE automatically uses:

* **Black** (formatting)
* **Ruff** (linting)
* **Syntax checker**
* **Pytest runner**
* **YAML validator** (for manifests and policies)

You can run validators manually:

```bash
poetry run core-admin check validate
```

*(If present — depends on your CLI setup)*

---

# 🔷 6. Governance & Policies

Policies are stored in:

```
.intent/policies/*.yaml
```

### **Load policies (Mind does this automatically)**

* `policy_loader.py`
* `policy_resolver.py`

### **Run specific governance checks**

```bash
poetry run core-admin check audit
```

Checks include:

* file headers
* imports
* domain boundaries
* ID & capability hygiene
* drift
* coverage
* runtime environment

---

# 🔷 7. Changing the Constitution

### **Never edit `.intent/` directly.**

Always follow the proposal workflow.

### **Create a proposal**

```bash
poetry run core-admin manage proposals new "Explain your change"
```

### **Generate a signing key**

```bash
poetry run core-admin keys keygen "your.email@example.com"
```

### **Apply canary audit**

CORE validates the proposed change against a temporary clone.

### **Human approval required**

No constitutional change can be self-applied by agents.

---

# 🔷 8. Knowledge Graph & Introspection

Knowledge is stored under:

```
.intent/knowledge/
```

Updated using:

```bash
poetry run core-admin manage database sync-knowledge
```

Tools involved:

* `symbol_index_builder.py`
* `knowledge_vectorizer.py`
* `graph_analysis_service.py`
* `semantic_clusterer.py`

Used for:

* capability discovery
* drift detection
* planning (future A2+)

---

# 🔷 9. Self-Healing Tools

Located in:

```
src/features/self_healing/
```

Key tools:

* `coverage_analyzer`
* `test_generator`
* `docstring_service`
* `header_service`
* `clarity_service`
* `complexity_filter`
* `id_tagging_service`
* `purge_legacy_tags_service`

Run automated improvement steps via:

```bash
poetry run core-admin fix all --dry-run
```

(lists what would be fixed)

Use smaller tools individually for precision.

---

# 🔷 10. Core Mental Models

### **Mind = Rules**

`.intent/` + governance engine.

### **Body = Execution**

All mechanical work: CLI, validators, services, crates.

### **Will = Autonomous Agents**

LLM reasoning, planning, coding — always governed.

### **Crates = Safe Sandboxes**

All autonomous changes happen inside crates until validated and audited.

### **Knowledge = Self-Understanding**

Symbols, capabilities, vectors, drift metrics.

---

# 🔷 11. Troubleshooting

### **Audit failing?**

Run with verbosity:

```bash
poetry run core-admin check audit --verbose
```

### **Imports failing?**

Check:

* import rules in `.intent/policies`
* domain boundaries

### **IDs missing?**

Run:

```bash
poetry run core-admin fix ids --write
```

### **Knowledge outdated?**

Run:

```bash
poetry run core-admin manage database sync-knowledge
```

### **Crate rejected?**

Inspect:

```
.core/crates/<id>/
validation_output/
audit_output/
```

---

# 🔷 12. When in Doubt

If you want a quick diagnostic:

```bash
poetry run core-admin inspect status
```

(If available in your CLI — otherwise use `check audit`.)

Or view CLI command tree:

```bash
poetry run core-admin inspect command-tree
```

---

# 📌 Final Reminder

CORE is a **governed system**.
Every action must respect:

* the Mind (rules),
* the Body (execution),
* the Will (agents),
* the Constitution (`.intent/`),
* and the Knowledge Graph.

This cheat sheet keeps you aligned with that governance.

If something in the documentation differs from how CORE behaves — treat it as a bug and fix it.

Welcome to the CORE development workflow.
