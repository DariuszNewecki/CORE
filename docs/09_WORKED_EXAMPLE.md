# 9. Worked Example: Your First Governed Application

The best way to understand CORE is to see it in action.
This guide walks you through creating a new, governed application and then demonstrates how CORE's "immune system" protects it.

> ⏱️ Estimated time: \~5 minutes

---

## Step 1: Create a New Application

From the root of the CORE repository, run the `new` command.
We'll create a simple **Quote of the Day API**.

```bash
poetry run core-admin new quote-api --profile default
```

This command scaffolds a complete, governed project inside the `work/` directory.

**What just happened?**
CORE created a new application with its own **Mind**—a pre-packaged `.intent/` directory that defines its architectural rules.

---

## Step 2: See the Generated "Mind"

Inspect the new project. You will see a file structure like this:

```
work/quote-api/
├── .intent/
│   ├── principles.yaml
│   ├── project_manifest.yaml
│   ├── safety_policies.yaml
│   └── source_structure.yaml
├── src/
│   └── ...
├── tests/
└── pyproject.toml
```

Inside `work/quote-api/.intent/source_structure.yaml`, you'll find the **architectural law** for this new app.
For example, it specifies that the `main` domain can only import from `shared`.

---

## Step 3: Intentionally Violate the Constitution

Now we’ll act as a developer making a common mistake.
We’ll add a feature to the `main` domain that incorrectly performs a direct file system operation—a task that belongs in a separate `services` domain.

Open the file:

```
work/quote-api/src/main/api.py
```

Add the following forbidden import and function at the top:

```python
import os  # ❌ Illegal import for the 'main' domain!

def log_quote_to_disk(quote: str):
    # Direct file I/O should be handled in a separate service.
    with open("/tmp/quotes.log", "a") as f:
        f.write(quote + "\n")
```

You’ve just introduced **architectural drift**.
In a normal project, this mistake might go unnoticed for months.

---

## Step 4: Run the Constitutional Audit

Now ask CORE to audit the new `quote-api` project.
The `byor-init` command can also run a **read-only audit** on any existing CORE-aware repository.

```bash
# From the root of the CORE repository
poetry run core-admin byor-init work/quote-api/
```

### Expected Output

You’ll see a constitutional failure.
The **ConstitutionalAuditor** has detected the illegal import because it violates the rules in `source_structure.yaml`.

```
[ERROR] 🚨 Domain Integrity Violation 🚨
File:    src/main/api.py
Domain:  'main'
Problem: Attempted to import 'os', which is not in the list of allowed imports for this domain.
```

---

## The Value Proposition

This is the **core** value proposition of CORE:

* Provides **automated, continuous architectural governance**.
* Catches errors that simple linters and formatters miss.
* Ensures the system evolves **in alignment with its declared intent**.
