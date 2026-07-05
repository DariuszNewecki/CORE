---
kind: adr
id: ADR-116
title: 'ADR-116 — GRC catalog residency: law-as-data, tiered by license, consumed not bundled'
status: accepted
---

<!-- path: .specs/decisions/ADR-116-grc-catalog-residency-and-licensing-tiers.md -->

# ADR-116 — The GRC catalog is licensed law-as-data: CORE consumes a tiered corpus, it does not contain the moat

**Status:** Accepted — governor-ratified 2026-06-19
**Date:** 2026-06-19
**Governing paper:** `.specs/papers/CORE-Disposition-Governance.md`
**Grounding paper:** `CORE-BYOR.md` — §9 grounding item 3 ("the document/records Repository type + **regulation→Intent representation** — the GRC second domain") — primary; §3 (the Repository as the single parametrization seam; F-41/F-42/F-43) — the seam this binds; §7 (the honesty guardrail) and §6 (GRC monetizes Reach at low autonomy) — why the corpus is the commercial center of gravity.
**Operationalizes:** the GRC gap-analysis service (Scenario 4 — the revenue priority). Supplies the **Intent** side of GRC gap-analysis; the customer brings the **Artifact** (their document corpus), CORE/us supply the licensed law.
**Relates:** ADR-113 (per-finding evidence class — what each catalog *check* declares) — distinct surface; this ADR governs where the catalog *lives*, ADR-113 governs how its findings are *labelled*. ADR-108/ADR-111 (external adoption, the `examples/starter-intent/` precedent for shipped reference data).
**Advances:** backlog T5b (`.specs/planning/CORE-BYOR-Program-Backlog.md`) — partially. The catalog (regulation→Intent) is decided here; the document/records **sensor type** (F-42 binding that reads a customer's records library) remains a sibling slice.

---

## Context

The governor has decided the GRC requirements catalog is **the proprietary,
maintained, licensed corpus** — the commercial moat and a standing obligation —
not open reference data. CORE's value is *trust made mechanical* (honest
per-finding provenance, ADR-113), and the catalog is the curated asset that trust
is sold around.

#678 shipped the first catalog (`nist_800_171_min.yaml`) under
`src/body/services/grc/catalogs/`, with `load_catalog()` reading
`Path(__file__).parent / "catalogs"`. That placement was a convenience of the
demo, and it is wrong on two counts:

1. **Layer.** A regulatory catalog is **law expressed as data** — the Intent side
   of gap-analysis, parsed into `ExecutableRule`s. CORE's architecture draws a hard
   line: `.intent/` is "governance law as data, never imported as Python"; `src/`
   is implementation. Law-as-data wearing a code-layer costume violates that split.
   (It is *not* CORE's own `.intent/` either — that is CORE's self-governance, not
   a customer-facing product corpus.)

2. **Exposure.** `DariuszNewecki/CORE` is a **public** repository. A licensed
   corpus committed in-tree enters public git history permanently — wheel exclusion
   does nothing about *source* visibility. The moat cannot be born in public git.

The data-residency model already recorded for GRC (on-prem for regulated buyers
whose data cannot leave; concierge otherwise) means the licensed bytes reach a
customer as an **entitlement**, not a git checkout.

## Decision

### D1 — The GRC catalog is law-as-data; it never lives in `src/` and is never CORE's `.intent/`
A catalog is the regulation→Intent representation (§9.3): CORE-authored checkable
requirements, parsed to `ExecutableRule`s. It is governed as data, edited without
code changes, and lives outside the implementation layer. It is a *Repository*
corpus CORE consumes through the §3 seam, not a module CORE contains.

### D2 — One unified corpus root, tiered by IP/license
The catalog corpus is a single root, `grc-catalogs/`, split into two tiers by
license status — the tier is a first-class directory axis because it is also the
access-control boundary:

```
grc-catalogs/
  public/                          # committed in CORE (public repo)
    <framework>/ catalog.yaml + provenance.yaml      # freely-accessible regulations: public-domain
                                                     # (NIST 800-171) and official-*-reusable law
                                                     # (GDPR, CFR Part 11, EU Annex 11, NIS2, CyFun)
  licensed/                        # the proprietary moat — NEVER committed to this public repo
    <framework>/ catalog.yaml + provenance.yaml      # ISO 27001, GAMP 5 (copyrighted/paywalled standards)
```

**Tier boundary (updated 2026-07-05, Phase 2 repo split):** the `public/` tier is not limited to
public-domain sources. It includes any framework whose source is *publicly accessible* — publicly-
accessible regulations (EU law, US CFR, EU GMP guidelines) ship in the public CORE repo. The `licensed/`
tier is reserved for *proprietary, copyrighted, or paywalled* standards (ISO, ISPE/GAMP) that cannot
be shipped without a commercial arrangement. The CORE-authored catalog content around a public source
is itself public; the catalog content around a paywalled source is commercial. This resolves the
apparent tension between the tier axis (commercial/access) and the OSS principle: freely-accessible
law is not a commercial moat, so its catalog is not withheld from OSS users.

The resolver enumerates `grc-catalogs/<tier>/<framework>/catalog.yaml` and is
tier-agnostic: `load_catalog(name)` does not know or care which tier a catalog
came from. (Tier names `public`/`licensed` are recommended over `free`/`comm` for
legibility; governor's call.)

### D3 — `licensed/` is population-method-agnostic; absent tier is honest, not an error
`licensed/` is a *resolved corpus root*, not a fixed delivery mechanism:
- **Dev:** populated as a git submodule of a private repo (recommended name
  `core-grc-catalogs`) — the corpus is itself a CORE-maintained, versioned,
  separately-licensed repository.
- **Deploy:** populated as the customer's **entitlement** — a versioned package or
  a read-only mount, gated by what they have licensed; never a git checkout, and
  not necessarily the full set of frameworks.

A public clone, ephemeral CI (ADR-115, no private creds), or a partial entitlement
yields an empty or partial `licensed/`. The resolver MUST treat this as *fewer
catalogs available*, never a failure. No committed `.gitmodules` is required in the
public repo if the governor prefers not to disclose the private repo's existence —
the population method is an environment concern, not a source-tree fact.

### D4 — CORE consumes via a resolved catalog root, not a path glued to the module
`_CATALOG_DIR = Path(__file__).parent / "catalogs"` is replaced by a catalog root
resolved through configuration and `PathResolver` (a new `catalog_resolver`). This
both decouples residency from the code layer and clears the
`no_hardcoded_runtime_dirs` smell the current literal carries. `load_catalog`'s
signature is unchanged.

### D5 — Every catalog carries machine-readable provenance; copyrighted text is never reproduced
Each `<framework>/` bears a `provenance.yaml` recording source, derivation method,
IP status, and version — the licensing and audit trail a licensed product requires.
For copyrighted standards (ISO, ISPE/GAMP 5) the catalog records **clause IDs and
CORE-authored paraphrases only; the source text is NOT reproduced** — the #678
discipline, made a machine-checkable property of every catalog rather than tribal
knowledge. A gap report cites the catalog name + version it ran against.

### D6 — Migration scope
`src/body/services/grc/catalogs/nist_800_171_min.yaml` (public-domain) moves to
`grc-catalogs/public/nist_800_171/`; the `src/` catalog directory is removed. The
`catalog_resolver` and the `_CATALOG_DIR` replacement land in the same change-set,
with the resolver's absent-tier behavior (D3) covered by a test. Whether the
`public/` tier is packaged into the published `core-runtime` wheel (so `pip`
adopters can run the demo) is a packaging decision settled in implementation, not a
property of this ADR.

### D7 — A declared inventory governs the corpus (appended 2026-06-19)
`grc-catalogs/inventory.yaml` is a single public manifest declaring every
framework CORE catalogs: its `tier` (`public` / `licensed` — confirming D2's
vocabulary), `ip_status`, approved `sources`, `fetch` depth, `revision`, and
`status` (`planned → approved → authored → published`). The `sources` list **is**
the retrieval whitelist as data — it operationalizes the rule that sources are
governor-approved before any fetch, replacing per-session approval with a
reviewed registry. `tier` (the commercial/access axis) is **orthogonal** to
`ip_status` (the source's copyright): GDPR is a `licensed` product built over an
`official-eu-law-reusable` source, so it may be fetched full-text while its
authored catalog stays in the licensed tier. A `published` entry MUST have a
matching `catalog.yaml` + `provenance.yaml` whose source agrees with the
manifest; an audit checks this and drift is a finding. Listing licensed-tier
frameworks in the public manifest is intentional — coverage is not the moat (the
authored requirement content is), so the registry doubles as a public
product-coverage view.

### D8 — Licensed-tier wiring resolved: tier boundary = repo boundary (appended 2026-06-19)
Closing the D2/D3 open choices, the licensed tier is wired so the access-control
boundary coincides 1:1 with GitHub repository visibility:

- The licensed catalogs live in a dedicated **private** repo, `core-grc-catalogs`
  (closes the repo-name choice), whose layout is `<framework>/{catalog,provenance}.yaml`.
- It is **cloned/mounted into `grc-catalogs/licensed/`**, which is **gitignored** in
  this public repo — **no git submodule, no committed `.gitmodules`** (closes the
  disclosure choice in D3's favour: the private repo is not disclosed in public
  CORE). Gitignoring also prevents a manual `add` or the autonomous daemon from
  scooping licensed bytes into a public commit.

Rejected the alternative ("one private repo holds *all* catalogs, free subset
*published* into CORE's public tier"): it duplicates the free catalogs across two
repos and needs a sync step + drift-guard. Tier-boundary = repo-boundary keeps
every catalog single-homed with zero duplication and no sync machinery — each
tier's home matches its visibility. No change to D2's model; this only selects the
mechanism D3 left open.

### D9 — The internal audit corpus: a third boundary, licence-gated (appended 2026-06-20)
D5 governs the *shipped catalog*: for copyrighted sources the catalog cites
clause identifiers and CORE-authored paraphrases only — the source's full text is
never reproduced there. D9 adds a boundary D5 did not contemplate: CORE's
**internal audit corpus** — the source PDF, its extracted text, and the vector
inputs CORE holds *internally* to reason against customer documents. This corpus
is an **input to findings, never an output**: CORE emits findings + clause
citations; it never serves the stored source text. D5's no-reproduction
discipline is therefore preserved unchanged — D9 permits *internal holding only*,
and only behind a satisfied licence gate.

- **Three boundaries, not two.** Orthogonal to D2's `public`/`licensed` tier
  axis (which is about *who receives a shipped catalog*), the internal corpus is
  about *what CORE holds to compute*. It ships to **no** tier — not public, not
  licensed-customers — and is **CORE-only**.
  - `public/<framework>/` — reusable catalogs, committed in CORE, everyone (D2).
  - `licensed/<framework>/` — metadata-only catalogs, paying customers; separate
    private repo, gitignored here (D8).
  - `internal/<framework>/` — full text + vector inputs, CORE-only; gitignored,
    never committed to any repo, populated only under a satisfied licence.

- **The licence gate.** For a `copyrighted` framework, populating `internal/`
  requires CORE to hold a **commercial/internal-use licence** from the
  rightsholder permitting use in an audit service — a stronger grant than a
  single-reader licence. The precondition is recorded as `internal_use_licence:
  required` on the framework's `inventory.yaml` entry (set on the copyrighted
  entries; absent where no licence applies, i.e. `public-domain` /
  `official-*-reusable`, which may be ingested freely). Ingesting copyrighted
  full text into `internal/` without a satisfied gate is a violation.

- **Per-framework internal layout.**
  ```
  internal/<framework>/
    source/        # the licensed source (e.g. PDF) — never shipped
    text/          # extracted plain text
    licence.yaml   # which internal_use_licence is satisfied, and its terms
  ```
  Vectors live in a per-framework Qdrant collection, not as files, queryable only
  by CORE's audit engine. The corpus is gitignored at `grc-catalogs/internal/`,
  mirroring D8's protection so neither a manual `add` nor the autonomous daemon
  can scoop the bytes into a commit.

This is a decision boundary only; the internal-corpus ingestion pipeline,
licence-gate enforcement, and Qdrant wiring are implementation work that follows
from this ratification.

## Consequences

- The moat never enters public git; its existence and contents are gated by
  entitlement, satisfying the regulated-buyer residency constraint by construction.
- `src/` returns to being pure implementation; the catalog joins the family of
  governed data corpora.
- A new top-level `grc-catalogs/` root is authorized by this ADR (it is outside the
  pre-existing sanctioned write surfaces by design — there is no correct existing
  home: not `.intent/` (CORE's own law), not `examples/` (a product, not a sample),
  not `var/` (runtime data), not `src/` (code)).
- Operational cost: dev clones, CI, and the daemon must tolerate an absent/partial
  `licensed/`; the submodule (dev) adds checkout ceremony. Bounded and accepted.
- The internal audit corpus (D9) is a third residency boundary, `grc-catalogs/internal/`,
  gitignored and CORE-only; like `licensed/` it may be absent/partial and the
  resolver must tolerate that. Holding copyrighted full text there is gated on a
  satisfied `internal_use_licence`; without it, CORE runs cite-only and the
  gap-analysis still functions (degraded, honest), never silently ungated.

## Alternatives considered

- **In-tree `licensed/`, excluded from the wheel at build time.** Rejected: a
  public repo makes the source itself the leak; build-config is the wrong boundary
  for a licensed asset, and one config edit away from exposure (the same
  config-divergence failure mode ADR-108 D4 just closed).
- **Separate private repo only, no `public/` tier in CORE.** Rejected: the OSS
  gap-analysis feature would have nothing runnable, and #678's NIST subset is
  genuinely public-domain and worth shipping as a demo.
- **Flat catalog directory, license tier as a `provenance.yaml` field.** Rejected:
  with no directory boundary you cannot separate the private bytes from the public
  ones — the tier split is load-bearing for access control, not cosmetic.

## References

- `CORE-BYOR.md` §3 (Repository seam, F-41/F-42/F-43), §9.3 (regulation→Intent), §6–§7 (Reach/honesty).
- ADR-113 (per-finding evidence class), ADR-108/ADR-111 (external adoption, `examples/` reference-data precedent).
- `.specs/planning/CORE-BYOR-Program-Backlog.md` — T5b.
- #678 (regulation-derived catalog-as-data; the provenance/no-reproduction discipline).
