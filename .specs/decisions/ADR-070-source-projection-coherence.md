---
kind: adr
id: ADR-070
title: ADR-070 — Source–Projection Coherence as Bounded Drift
status: accepted
---

# ADR-070 — Source–Projection Coherence as Bounded Drift

**Date:** 2026-05-24
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** None directly; reframes #441 as the first incremental delivery
**Related:** ADR-015 (consequence chain — orthogonal axis), ADR-016 (confidence floor — cognate pattern), ADR-018 (decomposed crawler/embedder), ADR-019 (commit reachability), ADR-030 (src/ stale-code DEGRADE), ADR-039 / ADR-060 (governance input staleness), ADR-066 (unmapped-rules invariant), ADR-069 (claim lifecycle lease semantics — cognate pattern)

---

## Context

CORE persists the same content across multiple representations. The
constitution lives on disk under `.intent/` and is also projected into
PostgreSQL (as the in-memory `IntentRepository` view that the auditor
consumes) and Qdrant (as the `core_policies` and `core-patterns` vector
collections that the LLM retrieves against). The source code lives in
`src/` and is projected into the knowledge graph (symbol tables,
`repo_artifacts`, and adjacent operational tables) and into the
`core-code` Qdrant collection. The architectural specs and decisions
live in `.specs/` and are projected into the `core_specs` Qdrant
collection.

Five surfaces, two of them sources of truth on disk
(`src/` + `.intent/` + `.specs/`), three of them derivations
(filesystem-backed view-state, PostgreSQL relational projections, Qdrant
vector projections). The system's correctness depends on these
representations agreeing — within bounds — at every moment a consumer
reads them. Today that agreement is asserted by a heterogeneous
patchwork of mechanisms with no common contract, no common signal
type, and no composite verdict surface.

### Three classes of failure when projections diverge silently

1. **Wrong context to the LLM.** `core-code` returns a vector for a
   deleted symbol; `core_policies` returns a vector for a retired rule;
   `core_specs` returns a vector for a since-amended ADR. The model
   produces plausible output against ghost evidence.

2. **Wrong governance decision.** `IntentRepository` serves a cached
   policy whose disk form has changed; an audit cycle produces a verdict
   under the prior rule set; the consequence chain attributes the
   verdict to the new rules. ADR-039 / ADR-060 partially close this for
   the audit-cycle path; the broader class is open.

3. **Operational churn against ghost work.** `repo_artifacts` holds a
   row for a deleted file; `RepoEmbedderWorker` warns once per cycle
   and continues; embedder bandwidth, vector-store quota, and log
   volume are wasted on work the system has already chosen not to do.
   #441 is the visible symptom — 350 such rows surfaced 2026-05-23.

### How the gap was found

#441 surfaced during the diagnostic session that produced ADR-069. The
ADR-069 session was investigating worker-claim orphans; the question
"what *else* is silently orphaned around here?" led to a raw SQL
inspection of `core.repo_artifacts`, which surfaced the 350-row pile.
**The system noticed and shrugged**: `RepoEmbedderWorker` had been
emitting `logger.warning("file missing")` 14 times per audit cycle for
an unknown duration. A `logger.warning` is not a constitutional signal —
no blackboard finding, no audit verdict change, no remediator pickup,
no governor inbox entry. Detection happened because a human, primed by
adjacent diagnostic work, inspected a table the audit surface does not
cover.

This is the same shape as the gap ADR-069 closed at the claim-lifecycle
layer: **validity inferred by external observation rather than declared
on the artifact itself.** ADR-016 refused the equivalent shortcut at
the confidence layer. ADR-069 refused it at the worker-ownership layer.
This ADR refuses it at the representation layer.

### Existing partial mechanisms

| Surface pair | Mechanism | Signal type |
|---|---|---|
| `src/` ↔ daemon's in-memory module set | ADR-030 detect-and-DEGRADE | Daemon state change |
| `src/` ↔ knowledge graph | `DbSyncWorker` ~5-min sync | Blackboard report |
| symbol DB ↔ Qdrant | `core-admin inspect drift` + `guard` commands | CLI invocation only |
| `.intent/` → audit reads | ADR-039 / ADR-060 reload-per-cycle | Audit-input cache invalidation |
| crawler → `repo_artifacts` (forward) | `RepoCrawlerWorker` | DB insert |
| `repo_artifacts` ↔ filesystem (reverse) | **None** | — |
| operational tables ↔ filesystem (general) | **None** | — |
| `.intent/` FS ↔ DB projection ↔ Qdrant `core_policies` / `core-patterns` | **No coherence verdict** | — |
| `.specs/` FS ↔ Qdrant `core_specs` | **No coherence verdict** | — |
| Composite "coherence verdict" surface | **None** | — |

Each existing mechanism handles one pair, on its own cadence, with its
own signal type. There is no common contract that says "this is a
projection of that, and here is how their agreement is verified and
bounded." The mechanisms have grown opportunistically as gaps were
noticed.

---

## Decision

### D1 — Representation coherence is constitutional, expressed as bounded drift

CORE declares the following property as constitutional:

> For every (source-of-truth, derived projection) pair in the declared
> inventory (D2), divergence between the source and the projection is
> **observable** through the audit/finding/remediation channels, and
> **bounded** by a constitutional value declared in `.intent/`. A pair
> whose actual drift exceeds its declared bound emits a finding;
> sustained excess triggers remediation; unobservable drift is a
> constitutional gap, not an operational accident.

The property is **bounded drift**, not identity. Sources of truth and
their projections are not synchronous: every projection has a sync
mechanism with a non-zero update window, and that window is the
acceptable drift. The constitutional claim is not "the representations
are identical at every instant" — that is impossible. It is "the
divergence is named, declared, observable, and held within a stated
bound that is itself a governance decision."

This matches ADR-016's posture (governance bounded in the model, not
asserted by surveillance) extended to the representation layer.

### D2 — Projection inventory: declared in `.intent/`

A new artifact `.intent/governance/projections.yaml` (governor-authored)
inventories every (source-of-truth, derived projection) pair the system
maintains. The minimum content per entry:

```yaml
- pair_id: "repo_artifacts ↔ filesystem"
  source_of_truth:
    kind: filesystem
    root: "src/"  # or absolute path / glob
  projection:
    kind: postgres_table
    locator: "core.repo_artifacts"
    join_key: "file_path"
  drift_bound:
    type: reference_set
    tolerance: 0  # any non-empty source ∖ projection or projection ∖ source is a finding
  sensor_worker: "repo_crawler"  # writer-as-sensor per D4; see D8 for the rationale
  remediation:
    mode: inline  # reap executed in the writer's existing cycle; no proposal pipeline
  authority: "RepoCrawlerWorker is the authoritative writer for this projection."
```

(The YAML above shows the writer-as-sensor / inline-remediation shape adopted by D8 for this specific pair. The other inventory shapes — independent sensor with `remediation.mode: proposal`, lease-style bound with `type: lease` and `lease_seconds`, hash-equality bound with `type: hash_equality` — are described in D3 and D4 and will appear in subsequent inventory entries as those pairs land.)

The inventory is **exhaustive in obligation**: a projection pair that
exists in the running system but not in the inventory is a constitutional
gap. The meta-rule in D5 cannot itself enumerate undeclared pairs — it
operates against the inventory — so the obligation to keep the inventory
complete is the governor's, surfaced through the operational-table sweep
in D9 and through periodic reconnaissance. This is the same posture as
ADR-066's unmapped-rules invariant (silence is not a valid signal) but
not the same mechanism: ADR-066 can enumerate active rules from the
registry; this ADR's inventory has no equivalent registry of projections
to enumerate against, so completeness is a governor obligation rather
than an automated check. A future ADR may introduce an automated
discovery mechanism (e.g., a code-side annotation that marks classes
as projections and lets a sensor cross-check against the inventory);
this ADR does not.

The five surfaces and the pair classes they generate:

| Class | Source of truth | Projection | Pair count (initial estimate) |
|---|---|---|---|
| Source code → knowledge graph | `src/` filesystem | PostgreSQL operational tables (`repo_artifacts`, symbol tables, …) | 3–5 |
| Source code → vectors | `src/` filesystem | Qdrant `core-code` collection | 1 |
| Constitution → governance read state | `.intent/` filesystem | `IntentRepository` cache + adjacent DB caches | 2–3 |
| Constitution → vectors | `.intent/` filesystem | Qdrant `core_policies`, `core-patterns` collections | 2 |
| Architectural decisions → vectors | `.specs/` filesystem | Qdrant `core_specs` collection | 1 |
| Knowledge graph ↔ vectors | PostgreSQL symbol tables | Qdrant `core-code` collection | 1 (already partially covered by `core-admin inspect drift`) |

Initial inventory authored once; subsequent additions land alongside
the projection they declare (a new operational table that mirrors a
filesystem subtree ships with its inventory entry in the same change).

### D3 — Each pair declares its drift bound

Every inventory entry carries a declared bound. The bound shape
depends on the pair class:

- **Lease-style bound** (most operational caches): `lease_seconds`
  — the maximum acceptable window between source change and projection
  catching up. Pattern from ADR-069 generalised. Suitable for
  `IntentRepository` cache and similar operational cache projections
  whose freshness obligation is time-bounded rather than set-bounded.
- **Hash-equality bound** (vector projections): the projection record
  carries a `source_hash`; the sensor compares against the current
  source hash. Suitable for `core_policies` / `core-patterns` /
  `core_specs` / `core-code`. Drift = hash mismatch; bound = the
  number of consecutive sensor cycles a mismatch may persist before
  remediation fires.
- **Reference-set bound** (set-difference projections): the projection
  must equal the source set; any element in projection ∖ source (orphan)
  or source ∖ projection (gap) is drift. The bound is "0" — a non-empty
  difference is a finding. Suitable for `repo_artifacts ↔ filesystem`
  (the #441 case).

There is no runtime fallback. The runtime never computes a default
bound. A projection without a declared bound fails inventory validation
and the system refuses to use it.

This matches ADR-069 D3: the lease/bound is a governance decision
belonging to the declaration, not a code-level constant. The shape
generalises; ADR-069 covered one specific pair (blackboard claims), this
ADR covers the pattern.

### D4 — Coherence sensors emit findings, not log warnings

Every projection pair has a declared sensor worker that runs on a
cadence appropriate to the bound (lease pairs at lease_seconds/2 or
less; hash pairs at the existing audit cadence; reference-set pairs on
filesystem-mutation cadence — typically piggybacked on the existing
crawler walks).

**Two sensor patterns are permitted, distinguished by the inventory
entry's `sensor_worker` and `remediation.mode` fields:**

- **Independent sensor (`remediation.mode: proposal`)** — the declared
  `sensor_worker` is a worker distinct from the projection's writer.
  The sensor walks the source and the projection, computes the diff,
  emits findings, and remediation flows through the existing proposal
  pipeline to a registered fix action. This is the default pattern and
  applies to lease-style and hash-equality bounds where the writer is
  not naturally producing the diff.

- **Writer-as-sensor (`remediation.mode: inline`)** — the declared
  `sensor_worker` IS the authoritative writer of the projection. The
  writer's existing cycle produces the diff naturally (its walk pass
  enumerates the source set), and the reap or sync executes inline in
  the same cycle as one extra DB operation. Findings are still posted
  to the blackboard for governor visibility and audit-trail attribution,
  but no proposal is dispatched because the writer is already
  constitutionally permitted to mutate the projection.

The writer-as-sensor pattern is permitted only for **reference-set
pairs whose writer's existing cycle naturally enumerates the source
set**. Splitting sensor and writer in this case would introduce a
redundant walk for no detection benefit and would split the projection
lifecycle across two authorities (a constitutional anti-pattern in its
own right — the issue body of #441 makes this argument concretely).
Lease-style and hash-equality bounds may not use the writer-as-sensor
pattern; their detection is necessarily out-of-band from the writer's
cycle, and the independent-sensor pattern is the only correct shape.

The sensor emits findings under a new `coherence.*` rule namespace.
Subjects follow the existing convention: `coherence.{pair_id}.drift`,
`coherence.{pair_id}.sensor_stale`. Severities default to:

| Drift class | Severity |
|---|---|
| Sensor not running | `HIGH` (the system cannot answer "is this coherent?") |
| Drift exceeds declared bound | `MEDIUM` |
| Drift within bound but trending toward it | `INFO` (advisory only) |

Findings flow through the existing `ViolationRemediatorWorker` → proposal
→ remediation pipeline. The current pattern of emitting `logger.warning`
(e.g., `repo_embedder_workers.py:112` for missing files) is explicitly
retired: log warnings remain for operator diagnosis but are not the
governance signal.

This satisfies the standing rule from ADR-066: silence is not a valid
default. A projection pair that is silently incoherent is a
constitutional violation, not an operational nuisance.

### D5 — Meta-rule: every declared projection pair must have an active sensor

A new audit rule `governance.coherence.all_pairs_sensed` enforces that
every entry in `.intent/governance/projections.yaml` has an active,
recently-heartbeating sensor worker. Behaviour:

1. Load the projection inventory.
2. For each pair: confirm the declared `sensor_worker` is registered,
   is not in `status: deprecated`, and has heartbeated within its
   declared interval.
3. Emit a `FAIL` finding (`severity: HIGH`) for any pair missing an
   active sensor.

This is the structural analogue of ADR-066's
`governance.remediation.all_rules_mapped` rule. Self-referential per
the same pattern: the meta-rule itself appears in
`auto_remediation.yaml` as a DELEGATE entry.

### D6 — Composite coherence verdict on the audit surface

`core-admin code audit` gains an advisory line after the standard
verdict block, parallel to ADR-067 D5's CCC line:

```
Representation Coherence: <N> pair(s) in-lease · <M> pair(s) drifted · <K> pair(s) sensor-stale
```

Format when all pairs in lease:

```
Representation Coherence: clean (<N> pairs · last check <YYYY-MM-DD HH:MM:SS>)
```

Format when inventory is empty (pre-first-pair state):

```
Representation Coherence: no pairs declared — see .intent/governance/projections.yaml
```

This line is advisory only. It has no effect on the PASS/FAIL audit
verdict, which continues to be driven by rule findings. The composite
line gives the operator a single readable signal of representation
health without needing to interpret per-pair findings.

### D7 — Existing partial mechanisms remain; their fit is documented, not retrofitted

The mechanisms in the Context table (`ADR-030` src/ stale DEGRADE,
ADR-039 / ADR-060 governance input staleness, `DbSyncWorker`,
`core-admin inspect drift`, `CommitReachabilityAuditor`) are not
re-implemented under this framework. Each continues to operate as
it does today. The inventory documents which pair each mechanism
covers, in what posture (the existing mechanism IS the sensor for
that pair, or supplements one). Examples:

- `ADR-030` is the sensor for `src/ ↔ daemon-in-memory-modules`.
  Bound: 0 (any drift triggers DEGRADE). Inventory entry references
  ADR-030 as the authority; no new sensor authored.
- `DbSyncWorker` is the sensor *plus the remediator* for
  `src/ ↔ knowledge graph`. Inventory entry references the worker;
  the framework adds the verdict-surface contribution but does not
  duplicate the sync mechanism.
- `core-admin inspect drift` becomes one of the read paths for the
  `symbol_DB ↔ Qdrant core-code` pair. No re-implementation.

Net effect: the existing investments are honoured. New work
fills documented gaps, not all gaps.

### D8 — First incremental delivery: `repo_artifacts ↔ filesystem` (closes #441)

The first projection pair to land under this framework is
`repo_artifacts ↔ filesystem`. The inventory entry, the writer-as-sensor
declaration on the crawler, and the bootstrap one-shot DELETE for the
existing 350 orphans are authored together in one change-set. #441
closes on landing.

**This delivery adopts the writer-as-sensor pattern (D4)** for the
`repo_artifacts ↔ filesystem` pair: `RepoCrawlerWorker` is declared as
both the sensor and the executor of the reap, because the crawler's
existing filesystem walk produces the source-set enumeration that the
diff requires. No separate `repo_coherence_sensor` worker is created.
The reap is one extra SQL operation appended to the existing walk pass
(`DELETE FROM repo_artifacts WHERE file_path NOT IN (current_walk_set)`),
not a fix action dispatched through the proposal pipeline. The choice
is recorded in the inventory entry's `remediation.mode: inline` field,
and the rule `coherence.repo_artifacts.drift` carries a DELEGATE entry
in `auto_remediation.yaml` (per ADR-066) with a description noting that
the writer-as-sensor pattern handles remediation in-cycle.

This sequencing matches the ADR-066 / `governance.remediation.all_rules_mapped`
pattern: an ADR establishes the constitutional invariant; the first
implementation lands the invariant's enforcement plus closes the
visible live case that motivated the ADR.

### D9 — Sequencing of subsequent pairs

Per-pair work is prioritised by **silent-blast-radius** — the size of
the hidden governance debt a drifted pair can produce before the gap
becomes visible by other means. Suggested order (not binding;
governor sequences):

1. `repo_artifacts ↔ filesystem` (D8 — closes #441; bounded; concrete)
2. `.intent/ ↔ IntentRepository` cache (closure of the post-ADR-060
   residual: `META/intent_tree.yaml` structural changes and `src/`
   Python changes still require restart per ADR-030; the framework
   makes that restart obligation observable as a coherence finding
   rather than a tribal-knowledge convention)
3. `.intent/ ↔ Qdrant core_policies / core-patterns` (vector
   coherence; hash-equality bound; affects LLM retrieval quality on
   governance questions)
4. `src/ ↔ Qdrant core-code` (vector coherence; hash-equality bound;
   affects LLM retrieval quality on code generation/refactor)
5. `.specs/ ↔ Qdrant core_specs` (vector coherence; affects ADR
   retrieval quality during architectural reasoning)
6. Operational-table sweep — identify other operational tables that
   reference filesystem paths and may exhibit the same #441 pattern
   (`agent_memory`, possibly others — inventory pass required)

The composite verdict surface (D6) becomes meaningful as pairs land;
in the interim it reports "N pairs declared" honestly.

---

## What this ADR does not do

- **Does not replace ADR-030.** Source-code drift continues to DEGRADE
  the daemon. The framework's contribution is to make that DEGRADE
  signal observable as a coherence verdict line, not to change the
  detection or response mechanism.
- **Does not replace the consequence chain (ADR-015 family).** The two
  axes are orthogonal: the consequence chain is *what happened ↔ what
  changed*; this ADR is *same content, multiple representations, must
  agree within declared bounds*.
- **Does not specify exact lease values for each pair.** Those are
  per-pair governance decisions that land in inventory entries, not
  in this ADR.
- **Does not specify the exact `coherence.*` rule schemas.** Those
  follow the existing rule-authoring conventions and land when each
  pair's enforcement does.
- **Does not implement automated remediation for every drift class.**
  Some pairs (vector hash-mismatch) have obvious remediators
  (re-embed); some (operational-table orphans) require fix actions
  that may not exist yet (`fix.repo_artifacts.reap_orphans` for D8
  is one such). Authoring of remediation actions is per-pair work,
  not this ADR's scope.
- **Does not change the audit verdict.** The composite coherence
  line is advisory. PASS/FAIL continues to be driven by rule
  findings under the existing severity → verdict mapping.

---

## Consequences

**Positive:**

- The constitutional claim "CORE is a governed software factory"
  becomes verifiable at the representation layer. An operator (or
  an auditor) can read a single line in the audit output and learn
  whether the system's representations of itself agree, instead of
  having to chase scattered drift signals across CLI commands, log
  files, and SQL queries.
- The "silent log-warning" anti-pattern (current state in
  `RepoEmbedderWorker`) is constitutionally retired. Future
  projection authors have a named obligation to declare the pair
  and its sensor before the projection ships.
- The pattern that ADR-016, ADR-069, ADR-066 each refused at their
  respective layers — *validity inferred by surveillance instead of
  declared on the artifact* — is now refused at the representation
  layer as well. The system's posture is consistent across all four
  axes.
- The Single-Governor Local deployment posture (ADR-068 D4) and the
  Track 7 GxP path (Band E) both depend on the system's ability to
  produce an evidence-grade self-audit. Representation coherence is
  a foundational input to that audit; the framework makes it
  evidence-grade rather than operationally inferred.

**Negative:**

- The inventory file is a new governor obligation. Every new
  projection pair authored anywhere in `src/` must have a matching
  inventory entry, sensor declaration, and remediation action (or
  declared DELEGATE) before the projection is allowed to populate
  the audit-clean baseline. This is a real surface-area increase
  on the governance side.
- The meta-rule (`governance.coherence.all_pairs_sensed`) will
  emit findings on day one of the framework's adoption — every
  existing projection pair that is not yet inventoried is in
  technical violation until inventoried. The remediation is "add
  the inventory entry," but the audit surface temporarily reflects
  the gap, which is honest but may look like a regression.
- The composite verdict line in `core-admin code audit` adds one
  more thing operators must read and interpret correctly. Mitigation:
  the line follows the ADR-067 D5 precedent shape exactly, so
  operators already familiar with the CCC line will read the
  coherence line the same way.
- Existing partial mechanisms must be documented as "the sensor
  for pair X." That documentation work has not been done. It is
  the entry cost of adopting the framework against existing
  investments.

**Neutral:**

- The framework does not by itself reduce drift. It makes drift
  observable, bounded, and remediable through the standard
  channels — but the system still has to do the sync work. The
  improvement is in governance posture, not in operational
  efficiency. (Operational efficiency may improve as silent log
  warnings become findings that pressure their underlying causes
  to be fixed; that is a downstream effect, not a direct one.)
- The ADR establishes a property; landing the property's first
  enforcement (D8) closes #441 and demonstrates the pattern, but
  full coverage across all five-surface pair classes is a
  multi-session arc. The framework being constitutional does not
  shortcut the per-pair work.

---

## Verification

Verification is staged. This ADR is verified at acceptance and at
first-delivery (D8); per-pair verification is per-inventory-entry
landing.

**At ADR acceptance:**

1. ADR-070 is committed at `.specs/decisions/ADR-070-source-projection-coherence.md`.
2. CORE-A3-plan.md's Architectural Decisions Made table carries a
   row for ADR-070 (per the standing session-close maintenance
   protocol).
3. `.intent/CHANGELOG.md` records the constitutional change.

**At first-delivery (D8):**

1. `.intent/governance/projections.yaml` exists and contains a
   well-formed entry for `repo_artifacts ↔ filesystem` with
   `drift_bound.type: reference_set`, `sensor_worker: repo_crawler`,
   and `remediation.mode: inline` (writer-as-sensor per D4).
2. `.intent/workers/repo_crawler.yaml` carries the inventory
   back-reference and a brief note that the worker is now declared
   as the sensor for this pair. No separate coherence-sensor worker
   is created.
3. `RepoCrawlerWorker`'s walk cycle includes the reap operation
   (`DELETE FROM repo_artifacts WHERE file_path NOT IN
   (current_walk_set)`). The rule `coherence.repo_artifacts.drift`
   has a DELEGATE entry in `.intent/enforcement/remediation/auto_remediation.yaml`
   per ADR-066, with a description noting that remediation is
   handled inline by the writer.
4. The bootstrap one-shot DELETE has run; the orphan count for
   `repo_artifacts` is 0.
5. A `core-admin code audit` run displays the composite
   coherence verdict line with at least one pair (the D8 pair).
6. #441 is closed referencing this ADR and the implementing
   commit.

**At meta-rule landing:**

1. `governance.coherence.all_pairs_sensed` is registered as an
   active audit rule with `severity: HIGH`.
2. The rule itself has a DELEGATE entry in
   `.intent/enforcement/remediation/auto_remediation.yaml`
   (self-referential, per ADR-066 precedent).
3. Audit emits a finding for every pair declared in
   `projections.yaml` that lacks an active sensor.

**Per-pair (recurring, not one-time):**

1. The pair is in the inventory with a declared bound.
2. The sensor worker is active and heartbeating.
3. The remediator (action or DELEGATE) is mapped.
4. The pair contributes to the composite coherence verdict line.

---

## Revisit triggers

- **A projection pair is found in the running system that is not
  in the inventory.** Undeclared pairs do not surface through D5 —
  D5 iterates the inventory and cannot enumerate what is not in it.
  Discovery of undeclared pairs is the governor's obligation,
  surfaced through the D9 operational-table sweep and through
  periodic reconnaissance (the same posture as ADR-066's
  silence-is-not-a-signal framing, but a different mechanism
  because no projection registry exists to enumerate against —
  see D2). When a missing pair is found, add the entry; consider
  whether the bound and remediation choices made for similar
  pairs apply.
- **A declared bound proves consistently inadequate** (sensors
  emit drift findings every cycle on a stable system). The bound
  is a governance decision; revisit it in `projections.yaml`. The
  framework's job is to make this re-tuning observable; it is not
  to tune the bound automatically.
- **A new persistence layer is added** (e.g., a third vector store
  for a new collection class, a separate operational database).
  The five-surface model in D2 is descriptive of current state;
  adding a new surface is an amendment to this ADR, not a routine
  addition.
- **The composite verdict line proves too coarse.** A drilldown
  CLI (`core-admin coherence status [pair_id]`) is a natural
  follow-up; this ADR leaves that as an implementation choice
  for the second or third pair delivery, when the value of the
  drilldown becomes empirically visible.

---

## References

- ADR-015 — Consequence chain attribution; the cognate
  "self-describing rather than externally-observed" pattern at the
  governance-state layer. This ADR extends the same pattern to the
  representation layer.
- ADR-016 — Confidence floor; cognate pattern at the
  confidence-classification layer.
- ADR-018 — Decomposed crawler/embedder; established the
  `repo_crawler` / `repo_embedder` worker split that this ADR
  builds on for the D8 delivery.
- ADR-019 — Commit reachability; the orphan-detection mechanism
  for the git-commit pair, precedent for inventory entry
  "existing mechanism is the sensor" pattern.
- ADR-030 — Daemon stale-code detect-and-DEGRADE; the sensor for
  the `src/ ↔ daemon-in-memory-modules` pair under this framework.
- ADR-039 / ADR-060 — Governance input staleness closure; sensors
  for the `.intent/ ↔ audit-cycle-cache` pair under this framework.
- ADR-066 — Unmapped-rules invariant; precedent for the
  "silence is not a valid default" framing and the meta-rule
  shape of D5.
- ADR-067 D5 — Constitutional Coherence Checker advisory line on
  audit output; precedent for the D6 verdict line format.
- ADR-068 D4 — Single-Governor Local deployment posture; depends
  on representation coherence for evidence-grade self-audit.
- ADR-069 — Claim lifecycle lease semantics; the immediate cognate
  pattern (lifecycle bound declared on the artifact) generalised
  in this ADR to the representation layer; the diagnostic session
  that produced ADR-069 also surfaced #441 (the gap this ADR's
  D8 closes).
- 21 CFR Part 11 §11.10(a) — controls for closed systems must
  ensure the authenticity, integrity, and confidentiality of
  electronic records. Representation coherence is the integrity
  half of this requirement at the system-internal level.
- EU AI Act Article 12 — record-keeping obligations require that
  high-risk AI systems "automatically record events ('logs')
  while the high-risk AI systems are operating." Silent
  representation drift falsifies the implied claim that the
  recorded events accurately reflect system state.
- #441 — `repo_artifacts: 350 orphaned rows for deleted files;
  crawler never reaps`; reframed by this ADR as the first
  incremental delivery (D8) rather than an isolated bug fix.
- `src/will/workers/repo_embedding/repo_embedder_workers.py:112`
  — the `if not full_path.exists(): continue` site whose
  current `logger.warning` is the canonical example of the
  constitutionally-invisible drift signal D4 retires.
- `src/will/workers/repo_crawler.py` — the worker whose
  reap extension is the D8 implementation site.
- `var/audits/repo_artifacts_orphans_2026-05-23.txt` — captured
  list of the 350 orphan rows that surfaced this gap.
