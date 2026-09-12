---
kind: planning
title: CORE — Repository Branch History
status: canonical
---

# Repository branch history

Record of retired branches whose lineage is preserved as a tag rather than a
live branch. Kept here because the tag alone won't explain itself once the
deletion is a few months old.

## `develop` — deleted 2026-09-12

`develop` (head `ec8411e7`, "feat: A2 autonomy achieved - autonomous code
generation operational", 2025-11-28) predated the repository restructure and
shared **no common ancestor** with `main` (`git merge-base` returned none).
231 commits existed only on that branch.

Before deletion, the full history was preserved as an annotated tag:

```
backup/develop-2025-11-28 -> ec8411e7d748c109269a209a2c95a92200350d50
```

The tag was pushed to `origin` and confirmed present via `git ls-remote`
before the branch was deleted, and an annotated local tag on the working
machine (`lira`) gives it a second independent copy of the objects. If this
tag is ever deleted, the commits become unreachable and GitHub will
eventually garbage-collect them — there is no other surviving copy of that
pre-restructure lineage.

No open pull request targeted `develop` as a base at deletion time
(`gh pr list --base develop --state open` was empty), so no PRs were
affected.

## Also deleted 2026-09-12

Both fully merged into `main` (ancestors, zero unique commits) — no tag
needed:

- `feat/isolated-consequence-chain-demo` (last commit 2026-07-26, ADR-155
  candidate work; content already reachable from `main`)
- `intent-meta-migration` (last commit 2025-12-27, migration already
  complete)
