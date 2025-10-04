# 5. Bring Your Own Repo (BYOR) Quickstart


The Guiding Principle: A Universal Auditor
CORE is designed to be impartial. It applies the same rigorous constitutional analysis to any repository that it applies to itself. This means CORE can analyze, understand, and help govern any project without special treatment.
This guide walks you through pointing CORE at an existing repository to generate a starter constitution for it.
The Goal: See Your Project Through CORE's Eyes
The core-admin byor-init command is a powerful introspection tool. It does not modify your code. Its purpose is to:
Analyze your repository's structure and existing # CAPABILITY tags.
Infer a set of architectural domains from your directory layout.
Propose a minimal, non-intrusive .intent/ constitution based on its findings.
This gives you an instant health check and a starting point for bringing your project under CORE's governance.
Step 1: The Safe Dry Run (Read-Only Analysis)
By default, the command runs in a safe, read-only dry run mode. It will show you what it would do without changing a single file.
Commands
code
Bash
# Analyze the current CORE repository itself
poetry run core-admin byor-init .

# Analyze a different project on your machine
poetry run core-admin byor-init /path/to/your/other/project
Understanding the Output
The command first builds a Knowledge Graph of the target repository. Then, it shows you the content of the constitutional files it proposes to create in a new .intent/ directory, including source_structure.yaml and project_manifest.yaml.
Step 2: Applying the Constitution (Write Mode)
Once you’ve reviewed the dry run output and you’re happy with the proposed constitution, run the command again with the --write flag. This will create the .intent/ directory and all proposed files inside your target repository.
Command
code
Bash
# Apply the starter constitution to the current repository
poetry run core-admin byor-init . --write
Step 3: The First Audit
Your target repository is now CORE-aware—it has a nascent "Mind." The next step is to ask CORE to perform its first constitutional audit. This will verify that your existing code aligns with the newly-declared principles.
Command
code
Bash
# Navigate into your project and run the audit
cd /path/to/your/other/project
poetry run core-admin system audit
The result is a continuous, automated health check on your project's architectural integrity. You can now use CORE's other commands (e.g., fix docstrings) to manage and evolve your project.
