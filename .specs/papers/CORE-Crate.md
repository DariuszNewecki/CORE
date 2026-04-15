<!-- path: .intent/papers/CORE-Crate.md -->

# CORE — The Crate

**Status:** Canonical
**Authority:** Constitution
**Scope:** All governed file mutation in CORE

---

## 1. Purpose

This paper defines the Crate — the unit of governed mutation in CORE.

No file in the live codebase may be modified except through a Crate.
This is not a convention. It is a constitutional boundary.

---

## 2. Definition

A Crate is a staged, sandboxed package of proposed file changes.

It contains:
- a manifest declaring intent, author, type, and the list of payload files
- the payload files at their target paths, relative to the crate root

A Crate is not a commit. It is not a patch. It is a proposal for mutation
that must pass validation before it reaches production.

---

## 3. Why the Crate Exists

Direct file writes are ungoverned. A component that writes directly to `src/`
bypasses IntentGuard, bypasses Canary, bypasses the audit trail. The result
is a change that cannot be validated, cannot be traced, and cannot be safely
reverted.

The Crate exists to make that impossible. Every mutation is staged first.
Staged changes can be inspected, validated, rejected, and archived — before
any production file is touched.

---

## 4. Lifecycle

create → inbox → canary validation → accepted or rejected

**create** — a Worker packs proposed file changes into a Crate via `crate.create`.
The Crate is written to `var/workflows/crates/inbox/{crate_id}/`.

**inbox** — the Crate exists but has not been applied. It may be inspected.
It may be rejected. Nothing in production has changed.

**canary validation** — the Canary Gate runs against the Crate in a sandbox.
If it passes, the Crate moves to accepted. If it fails, the Crate is rejected.
A rejected Crate is never applied.

**accepted** — the Crate's payload files are written to their target paths
in the live codebase. The Crate moves to `var/workflows/crates/accepted/`.

---

## 5. Constitutional Constraints

A Crate may not contain:
- absolute paths
- paths targeting `.intent/`
- paths targeting `var/keys/` or `var/cache/`
- path traversal sequences (`..`)

Violation of any constraint causes `crate.create` to fail before any file
is written. There is no partial creation.

---

## 6. Relationship to Other Concepts

- A **Proposal** authorizes the creation of a Crate. No Crate should be
  created without an authorizing Proposal.
- The **Canary** validates a Crate before it is applied.
- **IntentGuard** evaluates every file write that occurs during Crate creation
  and application.
- The **ConservationGate** evaluates LLM-produced content inside a Crate
  before Canary runs.

---

## 7. Non-Goals

This paper does not define:
- the internal format of the manifest beyond what is required for validation
- the Canary validation strategy
- rollback procedures after a failed application

Those are implementation concerns.
