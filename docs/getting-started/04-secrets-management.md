# Secrets Management

CORE supports a simple, local, developer-friendly secrets system.
It is intentionally minimal because CORE is a **governed development framework**, not a production secret vault.

Secrets are used for:

* LLM API keys (OpenAI, Anthropic, custom endpoints)
* Local provider configs
* Credentials required for autonomous development

Secrets are **never committed**, never leave your machine, and are optional unless you run autonomous tasks.

---

# 1. Where Secrets Are Stored

Secrets are stored locally (in your user environment), encrypted or obfuscated using the mechanism implemented under:

```
src/services/secrets_service.py
```

They are not:

* shared,
* synced,
* uploaded,
* committed.

This design ensures CORE stays portable and governance-safe.

---

# 2. Initializing Secrets

Before using any LLM-based autonomous functionality, initialize the secrets store:

```bash
poetry run core-admin secrets init
```

This creates a local secrets container appropriate for your environment.

---

# 3. Setting Secrets

Set a secret (e.g., LLM provider key):

```bash
poetry run core-admin secrets set OPENAI_API_KEY
```

You will be prompted to provide the value.

To set a custom provider key:

```bash
poetry run core-admin secrets set MY_PROVIDER_TOKEN
```

The key name is arbitrary — CORE passes secrets verbatim to LLM clients and providers.

---

# 4. Listing Secrets (If supported)

Some versions of the CLI may support:

```bash
poetry run core-admin secrets list
```

If not available, rely on the secrets file directly or re-set as needed.

---

# 5. Using Secrets in Autonomous Development

Once a key is set, autonomous workflows will automatically use it:

```bash
poetry run core-admin develop feature "Add diagnostics"
```

The Will (agents) will pull secrets from `secrets_service.py` when connecting to providers.

No additional configuration is needed unless using:

* custom endpoints,
* local Ollama servers,
* advanced provider setups.

---

# 6. Removing Secrets

If supported:

```bash
poetry run core-admin secrets unset OPENAI_API_KEY
```

Otherwise simply delete the secrets file from your local environment (location depends on OS).

This affects only your machine — no project files store secret values.

---

# 7. Security Principles

CORE follows clear rules about secrets:

### ✔ Secrets stay local

No syncing, no uploading, no commit.

### ✔ Secrets do not bypass governance

Agents cannot use undeclared or unapproved providers.

### ✔ Minimal footprint

CORE stores only what is needed for autonomous features.

### ✔ Reversible

You can wipe all secrets without affecting the repo.

---

# 8. Troubleshooting

### "No API key found"

Run:

```bash
poetry run core-admin secrets set OPENAI_API_KEY
```

### "Autonomy disabled"

Ensure the secrets are set and readable.

### "Provider authentication failed"

Verify:

* API key validity
* network connectivity
* provider availability

---

# 9. Summary

Secrets Management in CORE is:

* simple,
* local,
* safe,
* minimal,
* governed.

It enables LLM-powered features without compromising security or constitutional integrity.

Next steps:

* Return to **Starter Kits**
* Explore **CLI Workflows**
* Or continue to **Developer Contributing Guide**
