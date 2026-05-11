# ADR-036 — PathResolver excluded from modularity.needs_split

**Date:** 2026-05-11
**Status:** Accepted

## Decision

Add `src/shared/path_resolver.py` to the `excludes` list of the
`modularity.needs_split` enforcement mapping.

## Rationale

During the 2026-05-11 SRP refactor session, `path_resolver.py` was the
seventh and final `modularity.needs_split` candidate. Analysis (documented
in `var/splits/path_resolver_split.md`) established that the file is a
**catalog class** — ~30 trivial property getters returning `Path` objects,
one validation method, and four filesystem-search lookups. The rule fired on
volume (408 lines), not on lumped concerns.

The rule's `_detect_responsibilities` heuristic reported 2 signals, identical
to genuine multi-concern cases in the same session. The heuristic cannot
distinguish catalog bloat from genuine multi-concern at the same signal count.
Splitting the file would have added a mixin for 8 lines over the limit — a
cosmetic change that increases complexity without improving clarity.

The correct response is an exclusion, not a split. The file has one reason to
change: the runtime directory layout. That satisfies the SRP test.

## Removal condition

This exclusion is removed when `path_resolver.py` acquires a second genuine
concern — for example, if the filesystem-search lookups grow substantially
or a new category of path logic (e.g. remote path resolution) is added.
The exclusion is not a permanent waiver; it is a documented acknowledgment
that the current file is cohesive.

## Affected files

- `.intent/enforcement/mappings/code/modularity.yaml` — `excludes` entry added
  to `modularity.needs_split`.
