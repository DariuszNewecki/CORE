---
kind: adr
id: ADR-151
title: 'ADR-151 — The dead-shim reaper: declared-legacy ∧ zero-callers becomes a finding'
status: accepted
---

<!-- path: .specs/decisions/ADR-151-dead-shim-reaper.md -->

# ADR-151 — The dead-shim reaper: declared-legacy ∧ zero-callers becomes a finding

**Status:** Accepted — 2026-07-16
**Date:** 2026-07-16
**Grounds:** NorthStar — a system that cannot see its own dead weight cannot defend its
inventory; ADR-043 D7.2 (the legacy_signal pre-selector this completes); ADR-091 D2
(canonical sensor subjects, the detection vehicle); ADR-104/ADR-150 ramp discipline
(reporting first, promotion earned).
**Relates:** `modernization.legacy_signal` (reporting, regex pre-selector — stays as-is);
`modernization.legacy_scars` (advisory, LLM verdict — stays as-is); `purity.no_dead_code`
(reporting, vulture — file-local, no marker awareness); F-48.4 / ADR-088 (the published
`__all__` extension contract that defines the public-surface grace boundary); ADR-012 §2
(the retention-promise precedent). Tracking: #807 (external review 2026-07-16, finding T6;
epic #799; worked example #804).
**Supersedes:** nothing.

---

## Context

### The ladder tops out before it acts

CORE's legacy-enforcement ladder is: `modernization.legacy_signal` (reporting — a cheap
regex pre-selector that flags *files* carrying legacy/shim/deprecation markers) feeding
`modernization.legacy_scars` (advisory — an LLM review verdict). Nothing in that ladder
ever *escalates*: a finding is posted, a file is a "candidate for review," and the review
never has to happen.

The worked example is #804: six dead shims — a whole compatibility-shim module, a
"Deprecated alias." method, two path helpers whose own docstrings promised removal "after
one release cycle" (ADR-012 §2), and two orphaned ORM alias properties — were retired only
after an external review hand-found them. The shim module had lived **seven months**
(created 2025-12-10 in the Phase-2 merge) with `legacy_signal`'s markers matching it the
whole time. The signal fired; nothing had teeth.

### Why the join is the finding — neither fact alone works

Verified against the live knowledge graph (2026-07-16):

- **Zero-callers alone is over-broad.** `core.symbol_calls` (18,613 edges, refreshed by
  the ~5-minute sync cadence) shows **2,012 symbols with zero inbound call edges** — the
  overwhelming majority legitimate: CLI commands, route handlers, workers, registry- and
  decorator-dispatched actions, public contract surface. An orphan-sweep rule would be a
  false-positive storm.
- **Markers alone are already covered** — that is exactly `legacy_signal`, and its
  file-level candidacy verdict is the thing that proved toothless.
- **The conjunction is precise.** A symbol that *both* self-declares as
  legacy/deprecated/shim *and* has zero live callers has, by its own testimony, finished
  its retention purpose. All six #804 shims sat in exactly this intersection; none of the
  2,012 legitimate orphans carry deprecation markers.

### The dormant schema hook

The `core.symbols` table already models symbol-level deprecation: `state` and
`health_status` both know the value `'deprecated'`, and `v_orphan_symbols` already
*excludes* deprecated symbols. Verified: **zero rows** carry either value — the vocabulary
exists, nothing populates it. This ADR activates existing schema rather than inventing new.

### The honesty ceiling, stated up front (per the #801 precedent)

`symbol_calls` is a static graph. Dynamic dispatch — `getattr`, string-keyed registries,
config-file references — is invisible to it. "Zero inbound edges" is therefore *necessary
but not sufficient* evidence for deletion. The rule detects; the remediation must
re-verify (D4). #804's own discipline ("static zero-callers is necessary but not
sufficient — confirm no dynamic/string-based dispatch before removing") becomes the
encoded contract, not session lore.

---

## Decisions

**D1 — The finding is a conjunction: self-declared-deprecated ∧ zero live callers.** New
rule `modernization.dead_shim`: a public symbol that (a) **declares itself** the
deprecated artifact and (b) has zero inbound edges in `core.symbol_calls` (excluding
self-edges and edges originating in `tests/`) MUST be flagged as a dead shim.

The marker vocabulary is a closed **self-declaration** set — measured, not guessed (see
Verification): (i) a `.. deprecated::` docstring directive; (ii) a
`warnings.warn(..., DeprecationWarning)` in the body; (iii) a docstring that opens with
"DEPRECATED"/"Deprecated" or contains an explicit self-description — "deprecated
alias/shim", "compatibility shim", "backwards-compatible alias", "legacy-compatible
wrapper", "retained for one release". **Prose that merely mentions legacy does not
qualify** — `legacy_signal`'s broad regex, applied at symbol scope, intersects the orphan
set 60 times on today's tree, and the hits are fixers, converters, and migration tooling
that *process* legacy things (the purge-legacy-tags action, the legacy scanner itself).
That broad vocabulary stays what it is: a file-level pre-selector.

**Module→symbol attribution:** a module docstring carrying a self-declaration from set
(iii) (the `embedding_provider` shape — "Compatibility shim for legacy imports")
deprecates **every public symbol defined in that module**. A module docstring that merely
mentions legacy does not — the legacy *scanner's* own module ("Legacy Scanner Logic…")
is the measured counter-example.

**Properties are excluded from the automatic rule.** Attribute reads are not call edges:
the graph is structurally blind to a property's users, so zero-inbound-edges vouches
nothing for `@property` symbols (measured: a backwards-compat alias property intersects
as an orphan while sibling `.details`-style reads exist in the tree). Deprecated
properties fall to D4-style manual review, not automatic findings.

Neither half of the conjunction fires alone: markers-without-orphanhood stays
`legacy_signal`'s candidacy; orphanhood-without-markers stays silent (2,012 legitimate
zero-edge symbols prove why).

**D2 — Graph-invisible caller surfaces get grace; nothing else does.** Two symbol classes
have legitimate callers the static graph cannot see, and both are exempt from the
automatic finding:

- **The published extension contract** — symbols in the top-level package `__all__`s
  (F-48.4; currently 6 total: 5 in `shared`, 1 in `mind`; the other four packages export
  nothing). `core-runtime` ships on PyPI; external consumers are invisible to the graph,
  and ADR-012-style release-cycle retention exists precisely for them. (Boundary note:
  the grace is package-`__all__`-scoped — a deprecated *member* of an exported class is
  not itself exported and falls to D3's documented suppression, not automatic grace.)
- **Runtime-dispatch registrations** — Typer-registered CLI commands, FastAPI routes,
  `@register_action` actions. Their callers are humans and dispatchers, never static call
  edges (measured: four "DEPRECATED alias" CLI commands intersect as orphans today; all
  are deliberate UX transition shims whose retirement is a surface decision, not an
  automatic reap).

Everything else in `src/` has no invisible-caller excuse: with zero in-repo callers the
retention purpose is already served, and the finding fires without a grace period.
(ADR-012 called the cycle "bookmaking" when CORE had no external consumers; now that it
does, the boundary is the deliberately-minimal `__all__` contract plus the dispatch
surfaces.)

**D3 — Detection is a graph-backed sensor at reporting; the ramp is earned, not assumed.**
Detection cannot live in the file-scoped commit-gate engines — the join is cross-file and
DB-backed by nature. It ships as a sensor per the ADR-091 model (declaration + canonical
subjects `python::modernization.dead_shim::<symbol_path>`, `resolution_mechanism` per the
sensor contract), riding the graph the sync cadence already maintains. Enforcement starts
at **reporting**. Promotion toward blocking is a later decision gated on the observed
false-positive rate — the D1 conjunction *should* be precise, but the static-graph ceiling
(Context) means dynamic-dispatch false positives are possible and must be measured first.
The promotion gate must also re-run the intersection against deprecated symbols on
dispatch surfaces D2's grace list does *not* enumerate — registry-discovered workers,
ADR-091 sensors, `.intent/flows` entrypoints — because the grace list is enumerated, not
principled, and that class is where an unmeasured false positive would hide (none exist
on today's tree; the measurement would have surfaced them). Suppression for a deliberate
keep-alive uses the standard documented-exclusion mechanism with per-line rationale; no
new marker is invented.

**D4 — Remediation is verify-then-delete, encoded.** A dead-shim finding resolves by
governed deletion, and the deletion contract requires the dynamic-usage re-verification
first: grep for `getattr`/string-keyed dispatch/config and `.intent/` references to the
symbol name before removal, and remove the orphaned imports/warnings with it (the #804
procedure, as contract). First cycles route to the governor/Claude Code like #804 did;
autonomous remediation of this finding class is deferred until D3's precision is measured
— an imprecise auto-deleter is worse than no rule.

**D5 — The detection populates the dormant deprecation state.** When the D1 marker half
matches, the sync path records `state='deprecated'` on the symbol row — activating the
vocabulary `core.symbols` and `v_orphan_symbols` already carry but nothing writes. The
finding then joins marker-state against the call graph entirely inside the database, and
the existing orphan view stops excluding a value that never occurs.

---

## Implementation map (no constitutional-core surfaces)

| Surface | Authority | Change |
|---|---|---|
| `.intent/rules/architecture/modernization.json` | policy | add `modernization.dead_shim` (reporting) |
| `.intent/enforcement/mappings/architecture/modernization.yaml` | policy | mapping for the new rule |
| sensor declaration (`.intent/workers/` or sensor registry per ADR-091) | policy | declare the dead-shim sensor + subject format |
| sync path (marker detection → `symbols.state`) | code | populate `'deprecated'` per D5 |
| sensor worker (graph join query + finding post) | code | new, small; rides existing graph |
| tests | — | marker-detection cases; join-precision fixture matrix: **four positive** (#804's module-shape shim, deprecated-alias method, two path helpers) · **two property must-not-fire** (#804's `role_name`/`resource_name` ORM aliases — D1's property exclusion means they do NOT auto-fire) · **dispatch must-not-fire** (a "DEPRECATED alias" Typer command) · **prose must-not-fire** (the legacy scanner's module) · **the day-one live catch** (`sync_manifest`) |

## Consequences

**Positive.** The legacy ladder gains its missing final rung: self-declared-dead code with
no callers becomes a standing, visible finding instead of session lore — the six #804
shims would have been findings within one sync cadence of becoming orphans, not seven
months later. Dormant schema (`state='deprecated'`, the orphan view's exclusion) becomes
live. The public-surface grace makes the PyPI boundary explicit instead of implicit.

**Costs / obligations.** The real cost is not the join — it is the **symbol-scoped marker
attribution in the sync path** (D5): AST-level work deciding which symbol owns which
`.. deprecated::` / `DeprecationWarning` / docstring self-declaration, plus the
module→symbol attribution rule. That is where any bug in this ADR will live, and the
change-set should be scoped and tested accordingly; the sensor's DB join is the cheap
part. The marker set is a closed vocabulary and will miss creative deprecation prose —
acceptable; it can grow by mapping edit against the measured baseline. The static-graph
ceiling stands until/unless dynamic-dispatch edges ever land in the graph; D4's
re-verification is the compensating control. Promotion to blocking is a future decision
with its own evidence bar.

## Verification note

Written after verifying against the tree at `7d1cbaca` and the live database (2026-07-16):
`legacy_signal`/`legacy_scars` enforcement levels and marker patterns read from
`.intent/rules/architecture/modernization.json` + its mapping; `symbol_calls` = 18,613
edges; zero-inbound-edge symbols = 2,012; `symbols.state`/`health_status` `'deprecated'`
rows = 0 (dormant); `v_orphan_symbols` view definition confirmed to exclude the
never-written value; the shim module's 7-month lifespan from `git log --diff-filter=A`
(`49af6e64`, 2025-12-10). The six #804 shims (retired in `8a63cf44`) are the worked
example; as test fixtures they split per D1 — four positive catches, and the two ORM
alias *properties* as must-not-fire cases under the property exclusion.

**The precision claim was measured, not asserted — the intersection was run live
(2026-07-16), and it shaped D1/D2:**

- `legacy_signal`'s broad prose vocabulary at symbol scope: 128 marked symbols, **60 ∩
  orphans** — a false-positive storm of legacy-*processing* tooling (fixers, converters,
  the legacy scanner itself) and module-doc attribution spraying onto CLI commands. This
  is why D1 rejects prose-mention and why the broad set stays a file-level pre-selector.
- The strict self-declaration vocabulary: 23 marked, **10 ∩ orphans**, classified one by
  one: 4 = deliberately-retained "DEPRECATED alias" CLI commands (→ D2's dispatch-surface
  grace); 4 = the legacy scanner's own module ("Legacy Scanner Logic…" opener — → bare
  "legacy" openers dropped from set (iii)); 1 = a backwards-compat alias *property* (→
  D1's property exclusion: attribute reads are not call edges); 1 = **a genuine catch**:
  `cli/logic/sync_manifest.py::sync_manifest`, self-declared "deprecated and disabled,"
  zero references anywhere in `src/` or `tests/`.
- Net: **deployed against today's tree, the refined rule fires on exactly one symbol, and
  it is a true positive.** The rule therefore ships primarily as *prevention* — the #804
  shims were retired in `8a63cf44` before this ADR, so they are regression fixtures
  (four positive, two property must-not-fire), not live catches — with one live finding
  on day one.
