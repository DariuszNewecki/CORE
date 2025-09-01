# Migration Guide: Decentralized Capability System

## 1. Preamble: The Constitutional Mandate

This document outlines the formal, approved plan to migrate CORE's capability definition system from a monolithic file (`.intent/knowledge/capability_tags.yaml`) to a decentralized, domain-driven architecture. This change was mandated by a comprehensive architectural review which concluded that the existing system was a bottleneck to scalability, clarity, and the project's own constitutional principles.

This migration is a critical step in CORE's evolution, transforming a simple list into a structured, semantically-rich, and safely governable capability system.

## 2. The Target Architecture

-   **Decentralized:** Capabilities will be defined in `manifest.yaml` files within each architectural domain's directory (e.g., `src/core/manifest.yaml`).
-   **Semantically Rich:** Each capability will be a structured object with clear metadata (key, owner, risk_level, status, aliases).
-   **Cleanly Defined:** The public capability registry will only contain true, callable actions, not internal implementation details.
-   **Self-Validating:** The new structure will be enforced by formal JSON schemas and an upgraded Constitutional Auditor.

## 3. The Phased Migration Plan

### Phase 1: Discovery & Design (Timebox: 1-2 weeks)

-   **Goal:** Produce a data-driven blueprint for the new system before committing to the full migration.
-   **Actions:**
    1.  **Automated Analysis:** Audit the existing `capability_tags.yaml` to identify duplicates, high-risk capabilities, and inconsistent naming.
    2.  **Define Formal Domains & Cross-Cutting Concerns:** Finalize the official list of domains and document a strategy for handling shared capabilities.
    3.  **Design the Minimum Viable Schema:** Define the *essential* metadata for a capability (`key`, `description`, `owner`, `risk_level`, `status`, `aliases`) and create the enforcing `tag.schema.json`.
    4.  **Prototype & Validate:** Migrate a single, low-risk domain to prove the new loading mechanism works.
-   **Quality Gate:**
    -   ✅ The domain list and shared capability policy are documented and approved.
    -   ✅ The schema is finalized.
    -   ✅ The prototype successfully demonstrates the new logic.
    -   ✅ A detailed rollback plan for Phase 2 is documented.

### Phase 2: Incremental Migration (Timebox: 2-3 weeks)

-   **Goal:** Migrate all capabilities to the new structure, domain by domain, without disrupting system functionality.
-   **Actions:**
    1.  **Build Transitional Infrastructure:** Implement a **Dual-Format Loader** in the system that can read from *both* the old monolithic file and the new domain-specific files simultaneously.
    2.  **Migrate Domain by Domain:** Process each domain's capabilities, cleaning their semantics, enriching their metadata, and moving them to their new domain manifest. Add all old names to a central `aliases.yaml` for backward compatibility.
-   **Quality Gate (for each migrated domain):**
    -   ✅ All existing tool tests pass (`make test`).
    -   ✅ No capability references are broken.
    -   ✅ The new domain manifest file passes schema validation.
    -   ✅ **Rollback Trigger:** If any check fails, the migration for that domain is reverted, and the system continues to function using the old monolithic file via the dual-format loader.

### Phase 3: Finalization & Cleanup (Timebox: 1 week)

-   **Goal:** Complete the transition and make the new system the single source of truth.
-   **Actions:**
    1.  **Update All Consumers:** Modify all tools (Auditor, CLI, etc.) to use only the new multi-file system.
    2.  **Remove Legacy Artifacts:** Once all consumers are updated, remove the dual-format support from the loader and delete the old `capability_tags.yaml`.
    3.  **Update Documentation:** Ensure all project documentation is updated.
-   **Quality Gate:**
    -   ✅ 100% of capabilities are migrated.
    -   ✅ The old `capability_tags.yaml` file has been successfully removed.
    -   ✅ The full system audit (`make check`) passes cleanly.