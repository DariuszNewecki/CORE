# 2. The CORE Architecture

## The Mind-Body Problem, Solved

The central architectural pattern in CORE is a strict separation between the system's "Mind" and its "Body."

-   **The Mind (`.intent/`):** A declarative, version-controlled, and human-readable collection of files that represents the system's complete self-knowledge, purpose, and rules. It is the single source of truth for what the system *is* and *should be*.
-   **The Body (`src/`):** An imperative, executable collection of Python modules that acts upon the world. Its sole purpose is to carry out the will of the Mind, and its every action is governed by the rules declared within the Mind.

This separation is not just a convention; it is a constitutional law enforced by the system itself. The `ConstitutionalAuditor` is the bridge between the two, constantly ensuring the Body is in perfect alignment with the Mind.

## The Anatomy of the Mind (`.intent/`)

The `.intent/` directory is structured to provide a complete and transparent view of the system's governance.

| Directory | Purpose | Key Files |
|---|---|---|
| **`/mission`** | **The Constitution's Soul:** High-level, philosophical principles. | `principles.yaml`, `northstar.yaml` |
| **`/policies`** | **The Constitution's Laws:** Specific, machine-readable rules that govern agent behavior. | `safety_policies.yaml`, `intent_guard.yaml` |
| **`/knowledge`** | **The System's Self-Image:** Declarative knowledge about the system's own structure. | `knowledge_graph.json`, `source_structure.yaml` |
| **`/constitution`** | **The Machinery of Governance:** Defines the human operators and processes for changing the constitution. | `approvers.pub` |
| **`/proposals`** | **The Legislative Floor:** A safe, temporary "sandbox" for drafting and signing proposed constitutional changes. | `cr-*.yaml` |
| **`/config`** | **Environmental Awareness:** Declares the system's dependencies on its runtime environment. | `runtime_requirements.yaml` |
| **`/schemas`** | **The Blueprint:** JSON schemas that define the structure of the knowledge files. | `knowledge_graph_entry.schema.json` |

## The Anatomy of the Body (`src/`)

The `src/` directory is organized into strict architectural **domains**. These domains are defined in `.intent/knowledge/source_structure.yaml`, and cross-domain communication is tightly controlled by rules enforced by the `ConstitutionalAuditor`.

| Directory | Domain | Responsibility |
|---|---|---|
| **`/core`** | `core` | The central nervous system. Handles the main application loop, API, and core services like file handling and Git integration. |
| **`/agents`** | `agents` | The specialized AI actors. Contains the `PlannerAgent` and its related models and utilities. |
| **`/system`** | `system` | The machinery of self-governance. Contains the `ConstitutionalAuditor`, `core-admin` CLI, and introspection tools. |
| **`/shared`** | `shared` | The common library. Provides shared utilities like logging and configuration loading that are accessible by all other domains. |

## The Flow of Knowledge: From Code to Graph

The system's self-awareness is not magic; it is the result of a deliberate introspection process.

1.  **Code Annotation:** Developers (human or AI) annotate functions and classes with `# CAPABILITY:` tags to declare their purpose.
2.  **Introspection (`KnowledgeGraphBuilder`):** A dedicated tool (`codegraph_builder.py`) runs, scanning the entire `src/` directory. It uses Abstract Syntax Tree (AST) analysis to parse every file.
3.  **Knowledge Graph Creation:** It builds a comprehensive JSON file, `knowledge_graph.json`, which is a detailed map of every function, class, capability, and relationship in the codebase.
4.  **Constitutional Audit:** The `ConstitutionalAuditor` then uses this freshly generated Knowledge Graph as its primary source of truth to verify that the system's reality (the code) matches its declared intent (the constitution).

This loop—**Code → Introspect → Govern**—is fundamental to CORE's ability to evolve safely.