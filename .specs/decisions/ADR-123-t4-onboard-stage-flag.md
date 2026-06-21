---
kind: adr
id: ADR-123
title: ADR-123 — T4: `project onboard --stage` airlock flag and `project onboard promote`
status: accepted
---

<!-- path: .specs/decisions/ADR-123-t4-onboard-stage-flag.md -->

# ADR-123 — T4: `project onboard --stage` airlock and `project onboard promote`

**Status:** Accepted — governor-ratified 2026-06-21
**Date:** 2026-06-21
**Grounds:** `CORE-BYOR.md` §5 parameter 1 (read-only until invited); ADR-111 D3 (no overwrite safety invariant).
**Relates:** ADR-111 (amended by ADR-119) — onboard delivers the machinery floor; the airlock is an additive delivery mode, not a change to *what* is delivered.

---

## Context

`core-admin project onboard <path> --write` delivers the machinery floor directly into
`<path>/.intent/`. The existing safety rail (refuse if `.intent/` already exists, ADR-111 D3)
protects against accidental overwrite. What it does not protect against is the operator
delivering into a target repo without first reviewing the exact files that will land.

For regulated adoption paths (the GRC commercial context, any repo with an existing
governance structure the operator does not want surprised), the operator needs:

1. A preview richer than a dry-run log (actual files on disk, inspectable and diffable)
2. The ability to defer commitment to the target until ready — inspect, edit, confirm
3. A way to complete the delivery without repeating the onboard flags

T4 was deferred by the governor at 2026-06-17 pending a design choice between two
approaches: (a) `work/<name>/` staging airlock, (b) dry-run + refuse-if-exists as
sufficient. The governor has now decided: **`--stage` flag** (the two approaches
were not mutually exclusive; this ADR adds staging without removing the existing rails).

---

## Decision

### D1 — `--stage` flag: redirect write to `work/staged/<basename>/`

`core-admin project onboard <path> --write --stage` writes the machinery floor to
`work/staged/<basename>/` (CORE-repo-relative, already gitignored by `work/*`) instead
of directly into `<path>/.intent/`.

- `<basename>` is `Path(path).resolve().name` — the directory name of the target repo.
- The stage root is `<core_root>/work/staged/<basename>/`.
- Files land at `work/staged/<basename>/.intent/<rel>` — same relative structure as
  the direct-write output.
- `--stage` without `--write` is a no-op (dry-run already previews the delivery without
  writing; staging a dry-run produces no useful artifact).
- A second `--stage` run on the same basename overwrites the existing stage (idempotent
  re-staging from a fresh machinery floor source).

The operator inspects `work/staged/<basename>/`, runs `diff` or `tree` as needed, then
promotes or discards.

**Why `work/staged/` in CORE's repo, not in the target repo?**
Placing the stage inside CORE keeps it under the operator's control plane, away from the
target repo's own git tracking. The target repo owner never sees the stage artifact; the
operator owns the delivery timing. This is consistent with CORE's operator-managed
posture (no autonomous delivery into external repos without operator confirmation).

**Basename collision:** Two target repos sharing the same basename would overwrite each
other's stage. This is a rare operator scenario — typical operator workflow is one onboard
at a time. The mitigation is to sequence: stage → inspect → promote → stage next. No
engineering around this is warranted; the operator is the authority.

### D2 — `project onboard promote <path>` completes the airlock

A new `project onboard promote <path>` subcommand:

1. Resolves stage dir: `<core_root>/work/staged/<basename>/`
2. Refuses if `<path>/.intent/` already exists — same invariant as ADR-111 D3
   (overwriting an existing constitution is never automated)
3. Refuses if the stage dir does not exist — no silent no-op; the operator must
   have staged first
4. Copies all files from `work/staged/<basename>/.intent/` to `<path>/.intent/`
   via the `file.create` atomic action (same governed surface as the direct write)
5. Removes `work/staged/<basename>/` on successful promotion

Promote is always write-mode — there is no dry-run for promote. The staged content
is on disk and diffable before promote is called; the promote step is the explicit
commit and its effect is its own confirmation. Running promote twice on the same
target fails at step 2 (`.intent/` already exists), which is the correct refusal.

### D3 — Stage directory lifecycle (no GC)

Stage dirs are ephemeral (gitignored). No expiry, no GC daemon, no locking. The
operator manages them manually: inspect, promote, or `rm -rf work/staged/<name>` to
discard. This is consistent with the manual operator ownership model — the same
reason `grc ingest` has no autonomous re-ingestion trigger (ADR-122 D3 rationale).

A `project onboard list-staged` subcommand is explicitly out of scope for this ADR —
`ls work/staged/` is sufficient, and adding a thin wrapper around `ls` would add
surface without value.

### D4 — No change to what is delivered; no new delivery surface

The airlock is a mode change on the delivery *path*, not a change to the delivery
*content*. The machinery floor filter (`_MACHINERY_FLOOR_PREFIXES`), the source
resolution order, and the ADR-111 D3 safety invariants are unchanged. `--stage`
is additive; the direct-write path (`--write` without `--stage`) is unchanged.

---

## Consequences

- **The inspect-then-commit workflow is now first-class.** Operators who want to
  review before delivering can do so without building their own tooling around the
  dry-run log.
- **Promote reuses the governed write surface** (`file.create` via `ActionExecutor`),
  so the promotion step is constitutionally identical to a direct write — no new
  mutation surface, no new governance carve-out.
- **Direct-write path is unchanged** — operators who trust the machinery floor and
  do not need staging are unaffected. The flag is opt-in.
- **Basename collision is a known, accepted limitation.** Sequencing resolves it.
- **`work/staged/` is ephemeral by design.** Loss of the stage (manual rm, workspace
  wipe) is recoverable by re-running `--stage`.

## Alternatives considered

- **`--stage-dir <custom_path>` option for controlling the stage location.** Rejected:
  adds parameterisation complexity; `work/staged/` is the right default for CORE's
  operator model, and custom paths can always be handled at the OS level (symlinks).
- **Stage in the target repo (e.g. `<target>/work/.intent-staged/`).** Rejected:
  pollutes the target repo and requires the target repo owner to clean up what is
  CORE's staging artifact. CORE's operator model: CORE controls delivery timing,
  not the target repo.
- **`project onboard promote` as a top-level command.** Rejected: promote is
  conceptually part of the onboard lifecycle; grouping under `project onboard`
  keeps the workflow discoverable in `core-admin project onboard --help`.

## Implementation scope

- `src/cli/logic/byor.py` — add `stage_dir` parameter to `initialize_repository()`;
  new `promote_staged()` function
- `src/cli/resources/project/onboard.py` — add `--stage` option to `onboard_project`;
  add `promote` subcommand
- `tests/cli/logic/test_byor_stage.py` — stage writes to `work/staged/`, promote
  copies to target, promote refuses on existing `.intent/`, promote refuses on missing stage
