# CORE — Products

> Private/commercial. Not governed, not published.
> Inventory of what EXISTS is filled from project knowledge.
> The open-core LINE is a GOVERNOR decision — options only, no pick.

## What exists today (the product surface)
A single integrated runtime, decomposable into these real, shippable surfaces:

- **The governance runtime** — the constitution (`.intent/`), rules engine,
  phases (load -> parse -> interpret -> execution -> audit -> runtime), and the
  authorization layer. The core asset.
- **The audit engine** — runs inside `core-api`; constitutional auditor with a
  taxonomy of check engines (AST gate, regex gate, glob gate, CLI gate, workflow
  gate, LLM gate, knowledge gate). Produces findings with severity verdicts.
- **The autonomous remediation loop** — sensors detect violations; remediators
  propose fixes; the proposal pipeline authorizes and executes them; consequence
  chain is fully attributed.
- **The self-model** — a Postgres structural model of the repo (artifacts,
  symbols, call graph) plus vector stores (specs, code, policies, patterns) kept
  coherent by crawler/embedder workers.
- **`core-admin` CLI** — operator surface (audit, context build, drift inspect,
  etc.).
- **Governance API** (`core-api`) — programmatic access to audit/proposals/fix.
- **Capability-scoped filesystem authority** — chokepoint authorization so even
  the system's own writes are governed (IntentGuard, executor-token propagation).

## What's genuinely sellable vs. infrastructural
- **Sellable value:** the governance + audit + attribution loop. That's the
  thing nobody else has.
- **Infrastructural:** Postgres, vector store, LLM endpoint. Required to run, but
  not the value — and a friction source for adopters.

## Open-core boundary — DECIDED (2026-06-01)

The open/commercial line is now stamped per-feature in
**`.specs/papers/CORE-Features.md`** (the `Sourcing:` field on every F-NN entry,
plus the §4 summary table). That document is the authoritative contract — this
section is descriptive only.

**The shape, in one paragraph:** the entire engine ships open — governance
runtime, audit, autonomous remediation loop, full consequence chain, CLI,
worker/Blackboard, default rule library, and the extension *interfaces*
(F-41–F-43) so the plugin ecosystem can grow. The commercial product line is
the dashboard (F-20), multi-user state and identity (F-31, F-32, F-36),
multi-repo (F-33), web UI (F-34), federated constitution (F-35), regulatory
export (F-37), air-gap *guarantee* (F-38), SLA support (F-39), the OEM API
surface (F-40), and the four commercial extensions of shipping primitives
stamped by ADR-083 — premium rule libraries (F-44), hosted findings dashboard
(F-45), cloud audit export (F-46), managed Qdrant (F-47). Tally: **33 open /
15 commercial**.

This shape mirrors Postgres + extensions, VSCode + extensions, and Kubernetes +
operators: the open base is genuinely complete on its own merit, and the
commercial product line attaches via the same public interfaces a third party
would use. ADR-084 codifies the architectural shape; the closer analogues for
"what gets sold" remain Nagios Core / Nagios XI — polish, multi-tenant,
regulated-industry, and support.

**Commercial-surface shapes** (ADR-084 D1): every commercial feature takes one
of three structural shapes:

- **Plugin** — code that runs inside the open daemon, attached via an open
  extension interface (F-41/F-42/F-43, atomic action registry, `.intent/rules/`
  loader). Examples: F-37, F-44, F-46.
- **Sidecar** — standalone service that consumes the open repo's public APIs
  (F-40 OEM API surface) exclusively. Examples: F-20, F-34, F-45, F-47.
- **Runtime fork** — separate distribution depending on the open codebase as a
  published, versioned package, changing the runtime's authority/state model.
  Examples: F-31, F-32, F-33, F-35, F-36.

Two carve-outs sit outside the taxonomy: F-38 (air-gap guarantee) is a build
overlay; F-39 (SLA support) is not software. F-40 itself is the
sidecar-interface contract.

**Open-core honesty contract** (ADR-084 D7): four constitutional commitments
keep the architecture from drifting into the Elastic / MongoDB / HashiCorp
relicensing failure mode. They sit on equal footing with Features §1.

1. **Completeness.** The open base ships every primitive required to reproduce
   the full thesis. Reclassifying an `open` stamp is a governance amendment.
2. **Symmetry.** First-party commercial plugins/sidecars/forks use only public
   interfaces a third party could use. No commercial-only API surface in the
   open repo, ever.
3. **License floor.** MIT is the floor for the open repo. License tightening is
   forward-only and requires contributor consent.
4. **Library-grade openness.** The open codebase is published as
   semantic-versioned packages so that runtime forks — first-party and
   third-party — can depend on it as a library on equal terms.

**Enforceability** (the constraint flagged in the prior candidate table):
- Structural boundary by shape, not by single mega-repo (ADR-084 D5): up to
  five private repos (`CORE-rules-commercial/`, `CORE-plugins-commercial/`,
  `CORE-sidecars-commercial/`, `CORE-runtime-fork/`, `CORE-managed-infra/`),
  each scoped to the kind of code it hosts. Initial setup is rule-packs +
  plugins repos only — the others materialise when their first feature is
  authored.
- Open distribution license: **MIT** (decided; see `LICENSE` at repo root,
  copyright 2024). The README badges this publicly. MIT is the most permissive
  option — friendly to adoption, weak as a moat: a competitor can fork, close,
  and embed without contributing back. If the open-core commercial play later
  requires reciprocal terms (AGPL-style hosted-SaaS-loophole closure, or
  OEM/embedded re-licensing leverage), that is a forward-only decision —
  existing commits remain MIT, and only new contributions could carry
  different terms, with contributor consent. Treat MIT as the floor; any
  tightening is a deliberate future move, not a default. ADR-084 D7 §3
  reaffirms this commitment and explicitly forecloses the
  Elastic/MongoDB/HashiCorp relicensing pattern.
- Weakening any `open` stamp is a constitutional amendment, not a product
  decision, per the note in `CORE-Features.md` §1.
- Adding a commercial-only API surface to the open repo is forbidden by
  ADR-084 D6 (interface symmetry).

## Scope guard — what CORE is NOT
- Not a code generator. It governs one; the generator is swappable and
  provider-agnostic (local LLM models by default per ADR-052; external LLM
  providers opt-in per resource). Specific vendor selection is an operator
  preference, not a product dependency.
- Not a CI linter you bolt on. It's the production loop itself.
- GOVERNOR: name the other assumptions buyers will make that you must shut down.

## GOVERNOR decisions still open
- ~~Repo topology — overlay vs. separate `CORE-enterprise/` repo.~~ **Closed
  by ADR-084 D5** (2026-06-02): one private repo per shape (rules-commercial,
  plugins-commercial, sidecars-commercial, runtime-fork, managed-infra), with
  rules-commercial + plugins-commercial as initial setup. The single mega-repo
  option was rejected because shape determines license boundary, review
  cadence, and public-API dependency surface — collapsing them obscures the
  structural intent.
- Which of the 15 commercial features ships first as the inaugural SKU. With
  ADR-083 stamping F-44–F-47 and ADR-084 D8 classifying all 15 commercial
  features by shape, the sequencing constraint becomes structural:
  plugin-shape F-44 (premium rule packs) is the only commercial feature whose
  open dependencies (F-04 `.intent/` loader, F-05 default rule library) are
  already shipping — every other commercial feature waits on F-40 (sidecars),
  F-43 (plugin actions other than rule packs), or PyPI-published open packages
  (runtime forks). ADR-083 §Consequences and ADR-084 §Consequences converge on
  F-44 as the lowest-friction first deliverable from independent arguments
  (cost-to-deliver and structural-readiness). The decision belongs to the
  governor and is not closed, but the candidate set is no longer ambiguous.
- *(License resolved: MIT, see `LICENSE` and `Enforceability` above. Any
  future reciprocal-license consideration is forward-only and out of scope
  for the current commercial line.)*
