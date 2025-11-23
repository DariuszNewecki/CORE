# Bring Your Own Runtime (BYOR)

CORE is designed to operate in **any environment you choose** — local, virtualized, containerized, or embedded into larger systems.
This guide explains how to bring your own runtime while maintaining CORE’s governed, autonomous development model.

---

# 1. What BYOR Means in CORE

“Bring Your Own Runtime” means:

* You choose the Python environment.
* You control dependency resolution.
* You decide where CORE runs (local, VM, container, CI).
* CORE adapts by building context dynamically.

CORE does **not** require a special environment, special hardware, or cloud services.

The only hard requirement:

* Python 3.12+
* Poetry (for local development)
* A local LLM or API key (optional for autonomy)

---

# 2. Install CORE in Your Own Environment

## 2.1. Clone the Repository

```bash
git clone https://github.com/DariuszNewecki/CORE
cd CORE
```

## 2.2. Create a Virtual Environment

You may use any tool:

### Using `poetry` (recommended):

```bash
poetry install
```

### Using `venv` manually:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

# 3. Configure Your Runtime

## 3.1. Initialize Secrets

```bash
poetry run core-admin secrets init
```

(This stores local API keys for LLM providers.)

## 3.2. Optional — Configure an LLM Provider

You may:

* use local Ollama via `services/llm/providers/ollama.py`,
* or set an API key:

```bash
poetry run core-admin secrets set OPENAI_API_KEY
```

## 3.3. Run Initial Audit

```bash
poetry run core-admin check audit
```

This ensures your runtime meets CORE’s constitutional requirements.

---

# 4. Bring Your Own Tools

CORE integrates cleanly with:

* Docker
* Podman
* Kubernetes
* Proxmox VM environments
* local GPU/CPU setups

Since CORE does not rely on external state, you can:

* bundle it inside containers,
* mount volumes for knowledge stores,
* or include it inside CI/CD systems for pre-merge auditing.

---

# 5. Running Autonomous Development in BYOR Mode

A typical BYOR setup still supports autonomous generation:

```bash
poetry run core-admin develop feature "Add diagnostics route"
```

Internally, CORE:

* builds context from your local code,
* calls your configured runtime LLM,
* creates a crate,
* validates output,
* audits it,
* and produces a governed change.

No cloud dependencies unless *you* decide to use them.

---

# 6. Knowledge Store in BYOR Installations

The Knowledge Graph uses your local runtime database/engine:

* SQLite (default)
* PostgreSQL (if configured)

To rebuild knowledge:

```bash
poetry run core-admin manage database sync-knowledge
```

This allows CORE to adapt to:

* custom environments,
* local architectures,
* modified dependencies,
* bespoke tooling.

---

# 7. Example: Running CORE Inside a Docker Container

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install poetry && poetry install
CMD ["poetry", "run", "core-admin", "check", "audit"]
```

Run it:

```bash
docker build -t core/audit .
docker run core/audit
```

This runs a full constitutional audit in an isolated, reproducible environment.

---

# 8. CI Integration

In CI, the workflow typically looks like:

```yaml
- run: poetry install
- run: poetry run core-admin fix ids --write
- run: poetry run core-admin manage database sync-knowledge
- run: poetry run core-admin check audit
```

BYOR ensures CI uses the *same rules* and *same constitution* as developers.

---

# 9. Summary

BYOR allows you to:

* run CORE anywhere,
* use any local or cloud LLMs,
* embed CORE into CI/CD,
* maintain full governance,
* guarantee constitutional compliance.

Next:

* `03-batch-mode.md`
* `04-secrets-management.md`
