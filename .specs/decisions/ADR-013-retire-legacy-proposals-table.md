# ADR-013 — Retire core.proposals; Reserve Name for core.autonomous_proposals

**Date:** 2026-04-26
**Status:** Accepted
**Commits:** 107887b9 → cbc6820d (7-commit chain)

## Decision

`core.proposals` (the original constitutional file-replacement table with
cryptographic signing) is retired and dropped. It was never provisioned in
production — zero rows, no active writers, signing infrastructure
(`var/governance/approvers.yaml`, `var/keys/`) never created.

All proposal activity runs through `core.autonomous_proposals`, which is the
A3 pipeline's primary table and the only active proposal mechanism in CORE.

## What was removed

- DB tables: `core.proposals`, `core.proposal_signatures`
- DB column: `core.tasks.proposal_id` (FK constraints and column dropped)
- ORM: `Proposal`, `ProposalSignature` classes from `models/governance.py`
- Code: `src/cli/logic/proposals/` (service, canary, crypto, models)
- Code: `src/cli/logic/proposal_service.py`
- Code: `src/will/self_healing/refactoring_proposal_writer.py`
- Filesystem: `var/workflows/proposals/`

## Reserved name

The table name `core.proposals` is intentionally left free.

When `core.autonomous_proposals` is the only proposal mechanism in CORE —
and "autonomous" has become redundant because all proposals are autonomous —
`core.autonomous_proposals` should be renamed to `core.proposals`. The
qualifier should disappear with the distinction it described.

## Consequence

The two-table confusion that produced issue #144 (status enum mismatch,
tooling querying the wrong table) is eliminated. One proposal table, one
status enum, one code path.
