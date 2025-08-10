# Bring Your Own Repo (Including CORE)

**Principle: Ingestion Isomorphism.** CORE applies the same “attach → audit → propose → canary → ratify” pipeline to any repository — including CORE itself.

## Modes
- **Overlay mode** (no `.intent/` present): propose a minimal `.intent/` scaffold, capability tags, docstrings. No direct writes.
- **Respect & Critique mode** (`.intent/` present): use the repo’s own constitution, run audit, generate proposals with human-readable narratives.

## Safety
- Operates on a temporary copy; live repo is only updated via approved proposals.
- Canary must pass under the target repo’s own rules before any change applies.
- Idempotence: re-ingesting a clean repo yields zero deltas.

## Outputs
- **Intent narrative:** what this repo appears to do, where intent is unclear.
- **Governance diff:** gaps in policies/structure and minimal proposals.
- **Plan preview:** step sequence with pre/postconditions and proofs (tests, audit deltas).

## Acceptance Criteria
1) Self-ingest CORE (read-only): coherent narrative, no blocking proposals.
2) Self-ingest CORE (propose): only optional improvements; canary passes.
3) Double-run idempotence: second run produces no new proposals.
4) Foreign repo without `.intent/`: emits overlay proposals only.
5) Foreign repo with `.intent/`: respects its constitution/quorum/critical paths.
