# Start a Governed Project

This tutorial creates a new Python project that CORE governs, adds a set of rules,
and audits it. It needs **only Python 3.12+**: no database, no vector store, no LLM,
no running service.

You will finish with a project whose `.intent/` directory holds its law, and an audit
that enforces it.

## 1. Install CORE

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install "core-runtime>=2.11.0"
```

This installs `core-admin`, the command-line tool for running CORE on your machine.

## 2. Create the project

```bash
core-admin project new myproject --write
cd myproject
git init
```

`project new` creates a new directory and refuses an existing, non-empty one. It asks
for confirmation; answer `y`, or pipe the answer (`echo y | core-admin …`) in a script.

The project gets the **machinery floor**: the schemas, taxonomies and enforcement
configuration under `.intent/` that every governed repository carries. It gets **no
rules**. Rules are a choice you make in the next step.

## 3. Audit it — and see it refuse

```bash
core-admin code audit --offline
```

The audit fails. With no rules there is nothing to check, and CORE treats "nothing was
checked" as a failure, never as a pass.

## 4. Adopt a rule pack

```bash
core-admin project adopt-pack core/starter-python --write
git add -A && git commit -m "Adopt core/starter-python"
```

A pack is a ready-made set of rules. `core/starter-python` adds four, one of them
blocking. The packs that ship with CORE are `core/starter-python`, `core/python-hygiene`
and `core/architectural-boundaries`.

Commit the law before you audit. CORE judges the law of record: the `.intent/` committed
at `HEAD`. When `.intent/` has uncommitted changes, or the repository has no commit yet,
the audit cannot establish which law it evaluated, and the verdict is DEGRADED, never
PASS. (If git asks who you are, set `git config user.name` and `user.email` first.)

## 5. Audit again

```bash
core-admin code audit --offline
```

The audit now evaluates every rule in `.intent/` against the project and reports a
verdict. A **blocking** finding fails the audit; reporting and advisory findings are
listed without failing it.

## 6. Break a rule

The blocking starter rule, `starter.no_bare_except`, forbids swallowing exceptions.
Add a module that does exactly that:

```python
# src/myproject/risky.py
"""Example."""


def load(path: str) -> str:
    """Read a file."""
    try:
        with open(path) as f:
            return f.read()
    except:
        pass
    return ""
```

```bash
core-admin code audit --offline             # verdict FAIL, exit code 1: the rule and the line
core-admin code audit --offline --verbose   # ... and every file and location
```

Name the exception (`except OSError:`) and audit again: the verdict is PASS and the exit
code is 0. That loop — law in `.intent/`, an audit that enforces it, a verdict you can
act on — is what every other CORE path builds on.

## Where next

- Gate every pull request with the same audit: [Audit in CI](cold-reviewer.md).
- Add more rules: [Add a rule pack](adopt-a-pack.md).
- Govern a repository you already have: [Govern your own repository](byor-quickstart.md).
- See every option: [`core-admin` reference](reference/core-admin.md).
