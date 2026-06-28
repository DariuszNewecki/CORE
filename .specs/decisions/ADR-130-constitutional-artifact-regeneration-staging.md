---
kind: adr
id: ADR-130
title: ADR-130 — Constitutional artifact regeneration via governor-applied staging
status: accepted
---

<!-- path: .specs/decisions/ADR-130-constitutional-artifact-regeneration-staging.md -->

# ADR-130 — Constitutional artifact regeneration via governor-applied staging

**Date:** 2026-06-28
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-28 — drafted under governor direction)
**Closes:** #510
**Grounds:** ADR-077 §6 step 3; `governance.constitution.read_only`; `governance.mutation_surface.filehandler_required`
**Relates to:** ADR-023 D4, ADR-077, ADR-097 D4

---

## Context

`core-admin intent sync vocabulary --write` regenerates `.intent/META/vocabulary.json`
from the canonical section of `.specs/papers/CORE-Vocabulary.md`. It does so by
calling `Path.write_text()` directly on the `.intent/` path — bypassing both
FileHandler and IntentGuard's hard invariant.

Two provisional exclusions suppress the resulting audit violations:

```yaml
# governance_basics.yaml  (governance.constitution.read_only)
# mutation_surface.yaml   (governance.mutation_surface.filehandler_required)
- "src/cli/resources/intent/sync_vocabulary.py"
  # REMOVE when sanctioned .intent/ write-path lands (#510)
```

ADR-077 §6 step 3 anticipated one of two resolutions: route through a sanctioned
governor write-path, or keep an authority-scoped exception provisionally. The
provisional exception was chosen to unblock the Phase 2 drain; #510 was filed
for the proper resolution.

### Why a "sanctioned code write-path" is the wrong resolution

The hard invariant in IntentGuard — an unconditional block on all `.intent/`
writes — is not a technical choice to be routed around. It is what makes CORE
constitutionally governed. `.intent/` is human-authored: the governor writes it,
reviews it, and commits it. That invariant must hold for every path, every
caller, every impact value, every authority claim. The moment code can write to
`.intent/` — even via a named, audited, token-bearing pathway — the governance
frame is code-governed, not human-governed.

The correct resolution is therefore the opposite of creating a new code pathway:
the tool must stop writing to `.intent/` entirely.

### The right pattern: staging → governor applies

A regeneration tool produces derived content from a source-of-truth document.
The tool is deterministic; the governor is responsible for reviewing the output
and committing it to `.intent/`. The tool's job is to produce the output cleanly
and hand it to the governor. The governor's job is to apply it.

This is the draft-in-response pattern already established for all `.intent/` and
`.specs/` content in the development contract — applied here to a CLI tool rather
than a chat response.

---

## Decision

### D1 — Hard invariant is unconditional and permanent

IntentGuard's tier-1 block on `.intent/` writes is unconditional. No `impact`
parameter, authority annotation, governance token, or named method may bypass
it. ADR-097 D4's "governed-artifact API-mediated tier reserved for step 6" is
closed as `will-not-implement`: step 6 is not a bypass; there is no step 6.
This decision supersedes that placeholder.

### D2 — `sync vocabulary --write` renamed to `--stage`; output to `var/drafts/`

The `--write` flag is renamed to `--stage`. When invoked:

1. The regenerated JSON is written to `var/drafts/META/vocabulary.json` via
   `FileHandler.write()`. This path classifies as `runtime-output`; IntentGuard's
   hard invariant does not fire.
2. The tool prints the staging path and the exact apply command for the governor:
   ```
   ✓ Staged to var/drafts/META/vocabulary.json
   Apply with:
     cp var/drafts/META/vocabulary.json .intent/META/vocabulary.json
   ```
3. The governor reviews `var/drafts/META/vocabulary.json`, then applies and
   commits it as a normal `.intent/` file edit.

The `--write` flag is removed. Callers using `--write` will receive a clear error
directing them to `--stage`.

### D3 — Provisional exclusions removed

Both exclusions added for #507's Phase 2 drain are removed from
`governance_basics.yaml` and `mutation_surface.yaml`. No new exclusion is added:
`sync_vocabulary.py` no longer writes to `.intent/`, so neither rule fires.

### D4 — DEGRADED repair instruction updated

IntentGuard's DEGRADED suggested_fix and `artifact_gate.py`'s repair message
are updated to reflect the two-step repair:

```
Run: core-admin intent sync vocabulary --stage
Then apply: cp var/drafts/META/vocabulary.json .intent/META/vocabulary.json
```

### D5 — Canonical pattern for all derived constitutional artifacts

`vocabulary.json` is the first derived constitutional artifact; others are
anticipated (symbols-drift evidence, capability manifests). The canonical pattern
is established here:

- Regenerators write to `var/drafts/<mirror-of-target-path>` via FileHandler.
- The tool prints the staging path and `cp` apply command.
- The governor reviews, applies, and commits.
- No regenerator may write to `.intent/` or `.specs/` directly.

---

## Implementation

Change-set for the implementing commit:

1. **`src/cli/resources/intent/sync_vocabulary.py`**
   - Replace `--write` flag with `--stage`.
   - Remove `json_path.parent.mkdir(...)` and `json_path.write_text(...)`.
   - Write output to `var/drafts/META/vocabulary.json` via `FileHandler.write()`.
   - Print staging path and apply command.

2. **`src/body/governance/intent_guard.py`**
   - Update DEGRADED suggested_fix to the two-step instruction (D4).
   - Remove the ADR-097 D4 "step 6 reserved" comment; replace with D1 closure note.

3. **`src/mind/logic/engines/artifact_gate.py`**
   - Update repair message reference from `--write` to `--stage`.

4. **`src/shared/infrastructure/intent/vocabulary_projection.py`**
   - Update docstring reference from `--write` to `--stage`.

5. **`.intent/enforcement/mappings/architecture/governance_basics.yaml`**
   - Remove `sync_vocabulary.py` provisional exclusion.

6. **`.intent/enforcement/mappings/architecture/mutation_surface.yaml`**
   - Remove `sync_vocabulary.py` provisional exclusion.

---

## Verification

- `core-admin intent sync vocabulary --stage` writes to `var/drafts/META/vocabulary.json`, not to `.intent/`.
- `core-admin intent sync vocabulary --write` exits with a clear error.
- Running the audit engine against `sync_vocabulary.py` produces zero `governance.constitution.read_only` and zero `governance.mutation_surface.filehandler_required` findings.
- Applying the staged file (`cp var/drafts/META/vocabulary.json .intent/META/vocabulary.json`) and running `core-admin intent sync vocabulary` (dry-run) shows no diff.
- IntentGuard DEGRADED recovery: staging + manual apply restores the projection; subsequent writes are unblocked.
