# Project CORE: A Strategic Plan for Refactoring and Evolution

## 1. Preamble: From Diagnosis to Vision

This document outlines the strategic plan to evolve the CORE system from its current state to a truly self-governing, resilient, and evolvable architecture.

The initial feeling of "running in circles" was a correct diagnosis of a system struggling with internal inconsistencies. The recent comprehensive audit, while displaying numerous errors and warnings, was not a sign of failure. It was the **first successful act of self-diagnosis** by the system's nascent "brain." The audit provided a clear, actionable roadmap, revealing a fundamental disconnect between the declared `intent` and the `source code` reality.

This plan details the two major phases of our work:
*   **Part A: Foundational Refactoring.** To achieve a stable, constitutionally compliant baseline by fixing the issues diagnosed by the audit.
*   **Part B: Enabling True Self-Governance.** To build the necessary mechanisms for the system to evolve its own code and constitution safely and autonomously.

---

## Part A: Foundational Refactoring (Achieving Stability)

This phase focuses on acting on the audit's results to create a clean, consistent, and understandable codebase. It is the work required to teach the system what a "good" state looks like.

### Step A1: Unify the "Brain"
*   **Goal:** Eliminate data redundancy and create a single source of truth for the system's knowledge of its own code.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** The dual `codegraph.json` and `function_manifest.json` files have been replaced by a single, comprehensive `.intent/knowledge/knowledge_graph.json`. The `KnowledgeGraphBuilder` tool is now the sole producer of this artifact.

### Step A2: Consolidate Governance
*   **Goal:** Eliminate redundant tools and establish a single, authoritative script for verifying the system's integrity.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** The `ConstitutionalAuditor` is now the master tool for all static analysis. Older, fragmented tools (`architectural_auditor`, `principle_validator`, etc.) have been merged into it or deleted.

### Step A3: Stabilize the System
*   **Goal:** Ensure the system has a reliable safety net for development.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** The test suite has been repaired. Obsolete tests were deleted, and configuration issues (`pythonpath`, dependency conflicts) were resolved, resulting in a stable and passing test run.

### Step A4: Achieve Constitutional Compliance
*   **Goal:** Resolve all critical errors reported by the `ConstitutionalAuditor`.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** All structural errors (domain mismatches, illegal imports) have been fixed. The "mind-body problem" has been solved by manually annotating the existing codebase with `# CAPABILITY:` tags, fully aligning the `project_manifest.yaml` with the implementation. The audit now reports **ZERO critical errors.**

---

## Part B: The Path Forward (Enabling Evolution)

With a stable foundation, we can now build the mechanisms that allow CORE to fulfill its prime directive: to evolve itself safely.

### Step B1: Trust the Brain (Simplification & Cleanup)

*   **Goal:** Eliminate all audit warnings by making the system's "brain" more intelligent.
*   **Guiding Principle:** We did not blindly patch the auditor. Instead, we enhanced the `KnowledgeGraphBuilder` so it could understand more complex, valid code patterns, thus resolving the root cause of the false warnings.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** The `KnowledgeGraphBuilder` has been upgraded with a context-aware AST visitor and a declarative pattern-matching engine (`.intent/knowledge/entry_point_patterns.yaml`). It now correctly identifies inheritance, framework callbacks, and CLI entry points. All schema violations were corrected, and all code was fully documented. The `ConstitutionalAuditor` now reports **ZERO errors and ZERO warnings.**

### Step B2: Build the Immune System (Governed Creation)

*   **Goal:** Evolve the `PlannerAgent` to ensure that all *newly generated* code is automatically compliant with the constitution, preventing future errors.
*   **Status:** ✅ **COMPLETE**
*   **Outcome:** The `PlannerAgent._execute_task` method now follows a complete `Generate -> Govern -> Validate -> Self-Correct -> Write` loop. It automatically adds capability tags, enforces docstrings, validates the code, and triggers a self-correction cycle on any validation failure, ensuring only constitutionally compliant code is ever written to disk.

### Step B3: The Constitutional Amendment Process

*   **Goal:** Transform `.intent/` from a "notepad" into a true constitution with a formal, safe amendment process. This allows CORE to evolve its own brain.
*   **Status:** ✅ **COMPLETE**
*   **The Mechanism:**
    1.  **The Waiting Room (`.intent/proposals/`):** A dedicated directory for drafting changes to the constitution. Files here are not active.
    2.  **The Proposal Bundle:** A standardized YAML format for change requests (e.g., `cr-....yaml`) containing the `target_path`, `action`, `justification`, and proposed `content`.
    3.  **The Governance Layer:**
        *   **`IntentGuard`:** Enforces a new, critical rule: **No direct writes are allowed into `.intent/` except to the `proposals/` directory.**
        *   **`ConstitutionalAuditor`:** Scans `proposals/`, validates the format of any pending proposals, and reports them in a new "Pending Amendments" section of its report.
    4.  **The Ratification Mechanism (`core-admin` tool):** A human operator uses a simple CLI tool to manage the amendment lifecycle. The key command is `approve`.
    5.  **The "Canary" Pre-flight Check:** The `core-admin approve` command is designed to be fundamentally safe and solves the "how does it know it's broken if it's broken?" paradox.
        *   It spawns a **temporary, isolated "canary" instance** of CORE with the proposed change applied *in memory*.
        *   It commands this canary instance to run a full self-audit.
        *   If the canary audit succeeds, the change is permanently applied to the real `.intent/` directory.
        *   If the canary audit fails, the change is rejected, and the real `.intent/` directory is never touched, preventing system failure.

## 2. Conclusion

Upon completion of this plan, CORE will have evolved from a promising but inconsistent prototype into a robust, self-aware system. It will possess a stable foundation, a clear understanding of its own structure, and—most importantly—a safe, governed process for both creating code and evolving its own foundational intent.

This plan transforms CORE from a system that is merely *audited* to one that is truly *governed*.