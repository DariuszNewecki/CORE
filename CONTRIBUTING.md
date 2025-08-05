# Contributing to CORE

First off, thank you for considering a contribution. CORE is an ambitious project exploring a new frontier of self-governing software, and every contribution, from a simple bug report to a deep philosophical discussion, is incredibly valuable.

This document provides a guide for how you can get involved.

## The Philosophy: Principled Contributions

CORE is a system governed by a constitution. We ask that all contributions align with the principles laid out in our foundational documents. Before diving into code, we highly recommend reading:

1.  **[The CORE Philosophy (`docs/PHILOSOPHY.md`)](docs/PHILOSOPHY.md)**: To understand the "why" behind the project.
2.  **[The System Architecture (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)**: To understand the "how" of the Mind/Body separation.

The most important principle for contributors is `clarity_first`. Every change should make the system easier to understand, not harder.

## How You Can Contribute

There are many ways to contribute, and many of them don't involve writing a single line of code.

### 🏛️ Discussing Architecture and Governance

The most valuable contributions at this early stage are discussions about the core architecture and governance model.

-   **Review our Roadmap:** Read our **[Strategic Plan (`docs/ROADMAP.md`)](docs/ROADMAP.md)**.
-   **Open an Issue:** Find a challenge on the roadmap that interests you (e.g., "Scalability of the Manifest") and open an issue to discuss our proposed approach or suggest a new one.

### 🐞 Reporting Bugs

If you find a bug or a constitutional inconsistency, please open an issue. A great bug report includes:
-   The command you ran.
-   The full output, including the error and traceback.
-   Your analysis of why you think it's happening.

Our goal is for the system's `ConstitutionalAuditor` to catch all inconsistencies, but if you find one it missed, you've found a valuable way to make our immune system stronger!

### ✍️ Improving Documentation

If you find a part of our documentation confusing, unclear, or incomplete, a pull request to improve it is a massive contribution. Clear documentation is vital for the project's health.

### 💻 Contributing Code

If you'd like to contribute code, please follow these steps:

1.  Find an open issue that you'd like to work on (or open a new one for discussion).
2.  Fork the repository and create a new branch.
3.  **Write the code.** Ensure your code includes docstrings and type hints.
4.  **Run the checks.** Before submitting, please run the full introspection cycle to ensure your changes are constitutionally valid:
    ```bash
    # Install dependencies
    poetry install
    # Run the full self-audit
    python -m src.core.capabilities
    ```
5.  Submit a pull request.

---

We are excited to build this new future for software development with you.