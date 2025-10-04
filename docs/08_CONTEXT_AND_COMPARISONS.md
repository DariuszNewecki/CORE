# 8. Context and Comparisons

This document provides context for the CORE project by answering two key questions:
1.  What does a "governed application" built by CORE actually look like?
2.  How does CORE compare to other AI development tools?

## 1. What a "Governed Application" Looks Like

When you run `core-admin new my-app`, CORE doesn't just generate code. It creates a complete, self-contained, and **governed** project ecosystem.

Here’s what that means in practice:

*   **A Standardized Structure:** Your new project will have a clean, predictable layout (`src/`, `tests/`, `pyproject.toml`, etc.), making it easy for any developer to understand.

*   **A Nascent "Mind":** Most importantly, your new project gets its own `.intent/` directory. This is its constitution, seeded from a **Starter Kit**. It contains:
    *   `principles.yaml`: High-level values for your project.
    *   `source_structure.yaml`: The architectural rules for your codebase.
    *   `project_manifest.yaml`: A list of the capabilities your application is expected to have.
    *   `safety_policies.yaml`: Basic security rules to prevent unsafe code.

*   **An "Immune System" Ready to Go:** The new project is generated with a GitHub Actions CI workflow (`ci.yml`) that runs `black`, `ruff`, and `pytest` on every commit. It is CORE-aware and ready for you to add a `make audit` step to continuously check its constitutional alignment.

A "governed application" is one where the rules are not just in a wiki page; they are in a machine-readable format that an AI partner (like CORE) can understand, enforce, and even help you evolve.

---

## 2. How CORE Compares to Other Tools

CORE is often compared to other AI-assisted development tools. Here’s how it’s different.

| Tool | Primary Function | Core Paradigm |
| :--- | :--- | :--- |
| **GitHub Copilot / Cursor** | **Autocompletion & In-IDE Chat** | An AI assistant *for the developer*. It helps you write code faster by suggesting lines and functions. It has no knowledge of your project's overall architecture or long-term goals. |
| **AutoGPT / Agent Swarms** | **Autonomous Task Execution** | An AI agent that attempts to achieve a goal by breaking it down and executing steps. It is powerful but often unconstrained, with a high risk of producing incorrect, unsafe, or unmaintainable code. |
| **CORE** | **Governed System Architecture** | An AI partner *for the entire system*. CORE's primary job is not just to write code, but to ensure that all code—whether written by an AI or a human—remains in perfect alignment with a declared set of architectural and philosophical rules. |

**The Key Difference is Governance.**

-   Copilot is a **keyboard**. It makes you a faster typist.
-   AutoGPT is an **unsupervised intern**. It has a lot of energy but no discipline.
-   CORE is an **AI architect**. It helps you design the blueprint, then ensures everyone on the team (including other AIs) builds according to that blueprint.

CORE is designed for environments where **long-term maintainability, safety, and architectural integrity** are more important than the raw speed of code generation.
