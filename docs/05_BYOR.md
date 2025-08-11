--- START OF FILE ./docs/05_BYOR.md ---
# 5. Bring Your Own Repo (BYOR) Quickstart

## The Guiding Principle: Ingestion Isomorphism

CORE is designed to be impartial. It applies the same rigorous constitutional analysis to any repository that it applies to itself. This principle, known as **Ingestion Isomorphism**, means that CORE can analyze, understand, and help govern any project without special treatment.

This guide will walk you through the process of pointing CORE at an existing repository and generating a starter constitution for it.

## The Goal: See Your Project Through CORE's Eyes

The `core-admin byor-init` command is a powerful introspection tool. It does not modify your code. Its purpose is to:

1.  **Analyze** your repository's structure and capabilities.
2.  **Infer** a set of domains based on your directory layout.
3.  **Propose** a minimal, non-intrusive `.intent/` constitution based on its findings.

This gives you an instant "health check" and a starting point for bringing your project under CORE's governance.

---

## Step 1: The Safe Dry Run (Read-Only Analysis)

By default, the command runs in a safe, read-only "dry run" mode. It will show you what it would do without changing a single file.

**The Command:**
Navigate to your terminal and, from the CORE project's root directory, run the command, pointing it at the repository you want to analyze. To analyze CORE itself, you can simply use `.`.

```bash
# Analyze the current CORE repository
poetry run core-admin byor-init .

# Analyze a different project on your machine
poetry run core-admin byor-init /path/to/your/other/project