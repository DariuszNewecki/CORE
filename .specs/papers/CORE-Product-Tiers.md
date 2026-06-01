# CORE: Product Tier Architecture

**Document type:** Strategic paper
**Location:** `.specs/papers/CORE-Product-Tiers.md`
**Status:** Authoritative
**Author:** Dariusz Newecki
**Audience:** Internal — governance, commercial, investor

---

## 1. Purpose

This paper defines the five-tier product architecture of CORE and the principles that govern how tiers are structured, priced, and sequenced. It is the reference document for commercial representation, product planning, and investor conversation.

---

## 2. The Adoption Funnel

CORE is not sold top-down. The natural adoption path is:

**CI gate → Solo → Team → Enterprise or Embedded**

Each tier is a natural expansion of the previous. A developer encounters CORE Audit in a PR check. They install Solo to understand why. They convince their team to adopt Team. Eventually, a compliance officer asks whether CORE can produce evidence for a regulator. That is the funnel, not a sales motion — it is the architecture expressing itself as adoption.

The CI gate is the entry point for all of it.

---

## 3. What CORE Is Not Building

Three explicit exclusions govern every tier decision:

**No hosted SaaS where customer code transits external servers.** Regulated industries will not accept it. On-prem is the right default; cloud is opt-in for non-regulated customers only.

**No AI coding assistant positioning.** Cursor, Copilot, and Windsurf own the productivity tooling market. Competing there means being compared to the wrong products. CORE is governance infrastructure — the layer that makes AI-generated code trustworthy enough to deploy.

**No abstraction of constitution authoring.** The entire value proposition rests on humans writing law and machines enforcing it. Any product decision that hides or automates the `.intent/` layer weakens the core claim and destroys the audit defensibility that regulated customers are paying for.

---

## 4. The Five Tiers

### Tier 1 — CORE Audit (CI / lightweight gate)

A stateless audit engine deployable as a GitHub Action, GitLab CI step, or pre-commit hook. No daemon, no database, no workers. Customer supplies their `.intent/rules/` YAML (or uses the default rule library) and the engine evaluates each PR against the constitution.

**What it adds:** A deterministic governance gate at the merge point. Findings are reported as PR annotations. Merge is blocked on constitutional violations.

**What it does not include:** Consequence chain, autonomous remediation, workers, blackboard, or traceability beyond the CI run itself.

**Deployment:** pip package or Docker image. First findings visible within minutes of installation.

**Revenue model:** Open-source core. *Future commercial add-ons (not yet enumerated as features in `CORE-Features.md`):* premium rule libraries; hosted findings dashboard. These are monetisation mechanics under consideration; they will get F-IDs and `Sourcing: commercial` stamps when they crystallise into committed roadmap.

**Strategic role:** This is the top of the funnel. The cost of adoption is near zero. The purpose is to make CORE's governance visible to a developer who has not yet heard of CORE.

---

### Tier 2 — CORE Solo (full daemon, single repo)

The current reference implementation. Full daemon with workers, sensors, remediators, local Postgres and Qdrant via Docker Compose, local LLM or API key. Single governor, single repository, CLI-native. This is the proof-of-architecture tier — where CORE governs itself.

**What it adds over Audit:** Autonomous remediation loop, consequence chain (Finding → Proposal → Approval → Execution → Verification), blackboard, worker lifecycle, full CLI.

**Deployment:** Docker Compose on developer machine or private server.

**Revenue model:** Open-source. *Future commercial add-ons (not yet enumerated as features in `CORE-Features.md`):* cloud audit export; managed Qdrant. These are monetisation mechanics under consideration; they will get F-IDs and `Sourcing: commercial` stamps when they crystallise into committed roadmap.

**Strategic role:** This is where developers become believers. The consequence chain is the demo. A governor watches CORE detect a violation, generate a proposal, receive approval, execute the fix, and re-audit to confirmation — in a single session. That story is not available anywhere else.

---

### Tier 3 — CORE Team (shared infrastructure, multi-user)

Two to fifteen engineers sharing a single CORE instance with a shared Postgres. Designed for teams that have adopted AI-assisted development and need governance that operates at team scale.

**What it adds over Solo:**

- Shared consequence chain — all proposals, findings, and executions visible to the whole team
- Role-based constitutional authority — explicit governance over who can approve proposals and who can amend `.intent/`
- CI/CD gate — PR merge blocked on audit failure (Audit tier integrated as native gate)
- Web dashboard — convergence graph, proposal queue, audit history
- Multi-repository support
- Shared LLM backend

**The convergence graph** is CORE's unique team-level KPI: finding rate versus resolution rate over time. No other tool shows whether a codebase is moving toward or away from constitutional compliance over time. This is the anchor feature for team adoption. It answers the question every engineering manager actually needs answered: *"Is our AI-generated code getting better or worse?"*

**Deployment:** Self-hosted Docker stack. Cloud-hosted option for non-regulated customers.

**Revenue model:** Per-seat subscription, approximately €50–150 per seat per month.

---

### Tier 4 — CORE Enterprise (on-prem, regulated industries)

Pharmaceutical companies, medical device manufacturers, financial services institutions, defence contractors, and any organisation subject to GxP, IEC 62304, EU AI Act Articles 9 and 17, or equivalent regulatory frameworks.

**What it adds over Team:**

- Federated constitution — org-level root constitution, team-level extensions that inherit and cannot override root law
- SSO and RBAC via SAML and OIDC
- Audit export — structured, signed export of the full consequence chain (Finding → Proposal → Approval → Execution → Verification) formatted for regulatory submission
- Air-gapped mode — local-only LLM; code never leaves the customer perimeter
- SLA support

**The key repositioning at this tier:** the consequence chain is no longer a developer governance feature. It is the compliance evidence package. For a GxP customer, the consequence chain IS the Change Control documentation. For an EU AI Act Article 9 audit, it IS the risk management record. CORE does not replace GAMP 5, ALCOA+, or any regulatory framework — it is an instrument that, properly qualified, produces the evidence those frameworks require.

**Deployment:** On-prem Docker stack with customer-managed infrastructure.

**Revenue model:** Annual enterprise license, €50,000–€200,000 per year. Not per-seat. Compliance budgets do not think in seats; they think in systems and risk surface.

---

### Tier 5 — CORE Embedded (OEM / platform)

The long-term platform play. A third-party product — an IDE plugin, an AI coding platform, a GitHub App, a DevSecOps platform — embeds CORE's enforcement layer as middleware. The platform vendor's customers write their own constitutions; CORE enforces them without being visible as a separate product.

**What it requires:**

- Clean API surface (FastAPI layer already exists)
- Atomic action registry stabilised as a public contract
- Constitution schema versioned and documented for external authors

**Revenue model:** Platform license plus per-governed-execution fee or royalty arrangement.

**Strategic role:** This is the distribution multiplier. CORE reaches customers who will never install it directly. The constraint is that the API surface must be stable enough to make the integration reliable — this tier follows, rather than precedes, Team and Enterprise maturity.

---

## 5. Tier Comparison Summary

Feature IDs refer to `CORE-Features.md` — the canonical feature registry and
the authoritative open/commercial contract (`Sourcing:` field).

| Capability | Feature ID(s) | Audit | Solo | Team | Enterprise | Embedded |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Constitution enforcement (stateless) | F-01–F-07, F-10 | ● | ● | ● | ● | ● |
| Autonomous remediation loop | F-13 | | ● | ● | ● | ● |
| Consequence chain (full causal trace) | F-17, F-18 | | ● | ● | ● | ● |
| Multi-user / shared governance | F-31, F-32 | | | ● | ● | ● |
| Convergence graph dashboard | F-19 (metric), F-20 (UI) | | | ● | ● | ● |
| Federated constitution (org + team) | F-35 | | | | ● | ● |
| Regulatory export (GxP / EU AI Act) | F-37 | | | | ● | ● |
| Air-gapped / local-only LLM | F-27 (supported), F-38 (guaranteed) | | ○ | ○ | ● | ● |
| OEM API surface | F-40 | | | | | ● |

○ = supported with configuration, not default
● = included

For the full 43-feature x 5-tier matrix and `Sourcing:` stamps, see
`CORE-Features.md` §4 (registry) and §5 (tier mapping).

---

## 6. Positioning Statement (for commercial use)

CORE is not an AI coding assistant. It is not a code review tool. It is not a CI linter.

CORE is a **constitutionally-governed software factory** — a deterministic governance runtime that surrounds non-deterministic AI code generation with law, audit, consequence logging, and autonomous remediation. Humans write the law. CORE enforces it. AI is used as labor, never trusted as authority.

The correct comparable category is: policy-as-code + closed-loop remediation + consequence logging — a combination no adjacent tool covers fully or integrates as a runtime.

For regulated industries: CORE is the instrument that produces compliance evidence for AI-generated artefacts. It does not replace the regulatory framework. It produces the records the framework demands.

---

## 7. What Must Not Be Said

A commercial representative must not:

- Describe CORE as an AI assistant or copilot
- Claim CORE replaces human developers (it replaces human enforcement, not human judgment)
- Promise features from tiers that are not yet implemented (Embedded is a horizon play, not a shipping product)
- Represent CORE as a SaaS product without qualifying that customer code never transits external servers
- Use the phrase "we use AI to write code" without the full frame: "and a deterministic governance system to ensure that code is constitutional before it executes"
- Name any specific LLM provider (Anthropic, OpenAI, Ollama, Mistral, etc.) as a CORE dependency or default. CORE is provider-agnostic by architecture (`core.llm_resources` is per-resource per ADR-052) and the operator chooses. Refer to "LLM provider", "local LLM", "external LLM API" — never the vendor brand. *Exception:* naming a competitor's product (Claude Code, Cursor, Copilot) as a competitor or as the buyer's existing tool is fine; that is not vendor coupling.

---

*This document consolidates product tier decisions made in architectural sessions through May 2026. It supersedes any informal tier descriptions in chat history or planning notes.*
