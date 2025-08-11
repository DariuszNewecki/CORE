# 5. Bring Your Own Repo (BYOR) Quickstart

## The Guiding Principle: Ingestion Isomorphism

CORE is designed to be impartial. It applies the same rigorous constitutional analysis to any repository that it applies to itself. This principle, known as **Ingestion Isomorphism**, means that CORE can analyze, understand, and help govern any project without special treatment.

This guide will walk you through the process of pointing CORE at an existing repository and generating a starter constitution for it.

## The Goal: See Your Project Through CORE's Eyes

The `core-admin byor-init` command is a powerful introspection tool. It does not modify your code. Its purpose is to:

1. **Analyze** your repository's structure and capabilities.
2. **Infer** a set of domains based on your directory layout.
3. **Propose** a minimal, non-intrusive `.intent/` constitution based on its findings.

This gives you an instant health check and a starting point for bringing your project under CORE's governance.

---

## Step 1: The Safe Dry Run (Read-Only Analysis)

By default, the command runs in a safe, read-only **dry run** mode. It will show you what it would do **without changing a single file**.

**Commands**

```bash
# Analyze the current CORE repository
poetry run core-admin byor-init .

# Analyze a different project on your machine
poetry run core-admin byor-init /path/to/your/other/project
```

**Understanding the output**

The command first builds a Knowledge Graph of the target repository. Then, it shows the content of five constitutional files it proposes to create:

* `source_structure.yaml` — A map of your project, with each subdirectory in `src/` treated as a domain.
* `project_manifest.yaml` — An inventory of all the `# CAPABILITY` tags it discovered in your code.
* `capability_tags.yaml` — A dictionary for you to define and describe each of those capabilities.
* `principles.yaml` — A starter set of CORE's philosophical principles.
* `safety_policies.yaml` — A starter set of basic safety rules.

---

## Step 2: Applying the Constitution (Write Mode)

Once you’ve reviewed the dry run output and you’re happy with the proposed constitution, run the command again with the `--write` flag. This will create the `.intent/` directory and all proposed files inside your target repository.

**Command**

```bash
# Apply the starter constitution to the current repository
poetry run core-admin byor-init . --write
```

---

## Step 3: The First Audit

Your target repository is now **CORE-aware**—it has a nascent "Mind." The next step is to ask CORE to perform its first constitutional audit on the project.

From within the CORE project, configure the auditor to point at the new project. (In a future version, CORE will be able to attach to it directly.) The result is a continuous, automated health check on your project's architectural integrity and alignment with its newly declared principles.

This process is the first step in transforming any repository from a simple collection of code into a governed, self-aware system.
