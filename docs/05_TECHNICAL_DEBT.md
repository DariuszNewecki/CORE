# 05. Technical Debt Log & Architectural Notes

## Purpose

This document is the canonical log for known architectural debt within the CORE system. Its purpose is to make our process for managing and repaying this debt transparent, planned, and auditable, in accordance with our `clarity_first` and `evolvable_structure` principles.

This log was created in response to the highly effective `DuplicationCheck` audit that was enabled after our major refactoring. While the check produced ~200 warnings, these are not bugs but rather architectural smells that fall into distinct categories. This log prioritizes addressing them in a structured way without halting forward progress on strategic goals.

---

## Analysis of Duplication Warnings

The current set of `duplication.semantic.near_duplicate_found` warnings can be classified into three categories:

### Category 1: High Cohesion (False Positives)

These warnings flag a class as being semantically similar to its own methods. This is a sign of good design (high cohesion) and represents a limitation in the current sensitivity of the `DuplicationCheck`.

*   **Example:** `ThrottledParallelProcessor` is flagged as similar to its own methods (`run_async`, `run_sync`).
*   **Resolution:** Tune the `DuplicationCheck` to be less sensitive to intra-class or intra-module similarities.

### Category 2: Intentional Architectural Patterns (Acceptable Duplication)

These warnings flag thin CLI wrappers that are intentionally similar to the services they invoke. This is our chosen pattern to uphold `separation_of_concerns`.

*   **Example:** `cli/commands/diagnostics.py::policy_coverage` is flagged as similar to `features/governance/policy_coverage_service.py::run`.
*   **Resolution:** Add specific, permanent `symbol_ignores` to the `audit_ignore_policy.yaml` with clear justifications.

### Category 3: Legitimate Duplication (Actionable Debt)

These warnings have correctly identified genuine violations of our `dry_by_design` principle. They represent true technical debt that must be addressed.

*   **Example 1:** `knowledge_helpers.py::extract_source_code_from_ast` is a near-duplicate of `vectorization_service.py::_get_source_code`.
*   **Example 2:** `cli_utils.py::load_yaml_file` is a near-duplicate of a similar function in `cli_helpers.py`.
*   **Resolution:** Refactor and consolidate these duplicated functions into single, canonical services and update all call sites.

---

## Phase 4 Roadmap: Technical Debt Repayment & Hardening

The following tasks are formally scheduled to be addressed after the completion of the Phase 3 (Intent Crate) objective.

| Priority | Task Description                                     | Constitutional Principle Served | Status      |
| :---     | :---                                                 | :---                            | :---        |
| **1**    | **Consolidate Duplicated Helpers:** Refactor all Category 3 findings into canonical services. | `dry_by_design`                 | **Pending** |
| **2**    | **Tune the `DuplicationCheck`:** Modify the check to ignore high-cohesion (Category 1) false positives. | `clarity_first`                 | **Pending** |
| **3**    | **Codify Architectural Patterns:** Add specific `symbol_ignores` for acceptable (Category 2) patterns. | `separation_of_concerns`        | **Pending** |
| **4**    | **Remove Global Ignore:** Delete the temporary global ignore for `duplication.semantic.near_duplicate_found` from the policy. | `safe_by_default`               | **Pending** |
