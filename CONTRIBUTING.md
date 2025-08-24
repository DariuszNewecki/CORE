# Contributing to CORE

First off, thank you for considering a contribution. CORE is an ambitious project exploring a new frontier of self-governing software, and every contribution — from a simple bug report to a deep philosophical discussion — is incredibly valuable.

This document provides a guide for how you can get involved.

## The Philosophy: Principled Contributions

CORE is a system governed by a constitution. We ask that all contributions align with the principles laid out in our foundational documents. Before diving into code, we highly recommend reading the core docs in order:

1.  **[What is CORE? (`docs/00_WHAT_IS_CORE.md`)](docs/00_WHAT_IS_CORE.md)** — The high-level purpose and value proposition.
2.  **[The CORE Philosophy (`docs/01_PHILOSOPHY.md`)](docs/01_PHILOSOPHY.md)** — The principles and architecture.
3.  **[The Governance Model (`docs/03_GOVERNANCE.md`)](docs/03_GOVERNANCE.md)** — The process for safe, constitutional change.

The most important principle for contributors is `clarity_first`. Every change should make the system easier to understand, not harder.

---

## How You Can Contribute

There are many ways to contribute, and many of them don't involve writing a single line of code.

### 🏛️ Discussing Architecture and Governance

The most valuable contributions at this stage are discussions about the core architecture and governance model.

-   **Review our Roadmap:** Read our **[Project Roadmap (`docs/04_ROADMAP.md`)](docs/04_ROADMAP.md)**. Find a challenge that interests you and share your thoughts.
-   **Propose a Constitutional Change:** If you believe a principle or policy could be improved, open an issue to discuss it. The health of the system's "Mind" is our top priority.

### 🐞 Reporting Bugs

If you find a bug or a constitutional inconsistency, please open an issue. A great bug report includes:
-   The command you ran.
-   The full output, including the error and traceback.
-   Your analysis of why you think it's happening.

Our goal is for the system’s `ConstitutionalAuditor` to catch all inconsistencies. If you find one it missed, you’ve found a valuable way to make our immune system stronger!

### ✍️ Improving Documentation

If you find a part of our documentation confusing, unclear, or incomplete, a pull request to improve it is a massive contribution. Clear documentation is vital for the project's health and aligns with our `clarity_first` principle.

---

## 💻 Contributing Code

If you'd like to contribute code, please follow these steps.

### 1. Code Conventions

To uphold the `clarity_first` principle, all code submitted to CORE must adhere to these standards:

-   **Formatting:** All Python code is formatted with `black`. Our linter, `ruff`, is configured to follow `black`'s style. You can auto-format all code by running `make format`.
-   **Linting:** We use `ruff` to enforce code quality and best practices.
-   **Typing:** All functions and methods must have type hints.
-   **Docstrings:** Every public module, class, function, and method must have a docstring explaining its purpose.

### 2. Architectural Principles

To uphold the `separation_of_concerns` principle, the codebase is divided into strict architectural domains.

-   **Domain Definitions:** The domains and their responsibilities are defined in `.intent/knowledge/source_structure.yaml`.
-   **Import Rules:** A domain may only import from other domains listed in its `allowed_imports` list within that file. The `ConstitutionalAuditor` strictly enforces these boundaries. Before adding a new cross-domain import, you must first propose a change to the constitution.

### 3. Dependency Management

The project uses [Poetry](https://python-poetry.org/) to manage dependencies.

-   **Adding a dependency:** Use `poetry add <package_name>`.
-   **Adding a dev dependency:** Use `poetry add --group dev <package_name>`.
-   **Installation:** All dependencies are specified in `pyproject.toml` and locked in `poetry.lock`. A new contributor only needs to run `poetry install`.

### 4. The Submission Workflow

1.  Find an open issue that you'd like to work on (or open a new one for discussion).
2.  Fork the repository and create a new branch.
3.  **Write the code.** Ensure your code adheres to the conventions listed above.
4.  **Run the checks.** This is a critical step to ensure your contribution is constitutionally compliant.
    - For quick, iterative checks while you work, run `make fast-check`. This will handle linting and unit tests.
    - Before submitting, you **MUST** run the full suite, which includes the constitutional self-audit.
    ```bash
    make check
    ```
    If you have formatting issues, you can run `make format` to fix them automatically.
5.  Submit a pull request.

---

We are excited to build this new future for software development with you.