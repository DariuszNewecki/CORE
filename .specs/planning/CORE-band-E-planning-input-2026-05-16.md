# CORE — Band E Strategic Planning Input
# Enterprise Readiness Tracks
# Captured: 2026-05-16 | Status: Open — awaiting governor sequencing
# Status overlay refreshed 2026-05-24 (constitutional-prerequisite ADRs noted on Tracks 3 and 10)

---

## Purpose

This document captures the strategic tracks required to take CORE from
a governed autonomy runtime (A3 state, achieved) to a deployable
enterprise-grade product. It is the planning input for Band E
(Outward-Facing, milestone #17) and for the commercial roadmap.

Each track is self-contained. Tracks are not sequenced here — sequencing
is a governor decision. Open questions within each track are the inputs
to the ADRs that will govern that track.

---

## Track 1 — Operating Models

**What it is:** A complete, authoritative inventory of every supported
deployment topology, with a proven installation procedure for each.

**Operating models identified:**

| Model | Description | Key constraints |
|-------|-------------|-----------------|
| Single-governor local | One operator, daemon + DB on same machine or LAN. Current state. | No auth layer needed; trust boundary is the host. |
| Multi-operator server | Multiple operators sharing one CORE instance via API. | Requires auth, RBAC, per-request attribution (ADR-053 D7). |
| Air-gapped / GxP | Regulated environment, no external network, full audit trail. | LLM must be local (Ollama); no cloud API calls; compliance evidence package required. |
| CI-embedded | CORE called by a CI pipeline on every commit. | Headless; API-only; no interactive approval; governor-defined auto-approve policy. |
| Multi-project | One CORE instance governing multiple codebases. | Namespace isolation per project; DB partitioning question. |

**Open questions:**
- Is multi-project in scope for v1 Enterprise, or deferred?
- Does air-gapped require a separate installation artifact (no PyPI)?
- What is the minimum hardware spec per model?

**ADR trigger:** One ADR per operating model, or one ADR covering all
with per-model annexes. Governor to decide.

---

## Track 2 — Installation & Upgrade

**What it is:** A proven, documented, repeatable installation procedure
for each operating model. Includes first-run, upgrade, and rollback.

**Components:**
- Pre-flight checklist (Python version, DB, Ollama, disk space)
- Installation script or package (pip, Docker, Ansible — TBD)
- First-run wizard (DB init, `.intent/` scaffold, first audit)
- Upgrade path — DB schema migration procedure between versions
- Rollback procedure — what to do when an upgrade fails
- Health check / readiness probe — how to confirm installation succeeded

**Open questions:**
- Is Docker the primary distribution artifact for server/GxP models?
- Who owns DB migration execution — CORE CLI, Alembic, or a separate
  migration tool?
- What is the rollback guarantee — last known good schema only, or
  arbitrary version?

**ADR trigger:** Installation architecture ADR before any packaging work.

---

## Track 3 — User Management & Access Control

**What it is:** Authentication, authorization, and role model for
multi-operator deployments. Required before any API is exposed beyond
localhost.

**Role model (draft):**

| Role | Permissions |
|------|-------------|
| Governor | Full access — approve/reject proposals, accept ADRs, modify `.intent/`, trigger any operation. |
| Operator | Read all state, trigger read-only operations (audit, inspect, coverage). Cannot approve proposals or modify constitution. |
| Read-only Auditor | Read audit findings, consequence chain, compliance evidence. No write access. GxP auditor archetype (GxP early adopter (pharma, Belgium)'s QA role). |
| CI System | Submit long-running operations (audit runs) via API key. Cannot approve proposals. |

**Components:**
- Authentication model — API key (v1), mTLS or OAuth (later)
- RBAC enforcement in API layer
- Per-request attribution (`requested_by` — ADR-053 D7)
- API key lifecycle — issuance, rotation, revocation
- Audit trail of access — who called what, when

**Open questions:**
- Is single-governor local exempt from auth entirely (localhost trust)?
- Does the governor role require MFA for GxP deployments?
- How are API keys stored — hashed in DB, or external secrets manager?
- Is SSO (SAML, OIDC) in scope for Enterprise tier?

**ADR trigger:** Auth model ADR (deferred in ADR-053; trigger is first
multi-user or remote-access use case).

**Status (2026-05-24):** Constitutional prerequisite landed —
**ADR-068 (Principal Role Taxonomy)** 2026-05-22 declares the four-role
taxonomy (`principal.governor`, `principal.operator`, `principal.auditor`,
`principal.system`), the three-layer model (taxonomy / binding / enforcement),
the SoD constraint, and the Single-Governor Local deployment posture. ADR-068
explicitly notes: *"this ADR is the constitutional prerequisite, not the full
Track 3 delivery."* The auth model itself (API key lifecycle, RBAC
enforcement, mTLS) remains the open ADR trigger.

---

## Track 4 — Documentation Automation

**What it is:** Automated generation and maintenance of all operator-
facing documentation from CORE's own governed artifacts.

**Document types:**

| Document | Source | Audience |
|----------|--------|----------|
| API Reference | Pydantic schemas + FastAPI OpenAPI | Operators, integrators |
| User Manual | `.intent/` + ADR index + capability map | Governors, operators |
| Administrator Guide | Operating model specs + installation procedures | IT / DevOps |
| Release Notes | CHANGELOG + ADR index + commit log | All |
| Constitutional Audit Report | `core.audit_findings` + consequence chain | GxP auditors, regulators |
| Compliance Evidence Package | Audit trail + proposal chain + ADR log | EU AI Act Art. 9/17; GxP IQ/OQ/PQ |

**CORE-specific opportunity:** CORE already has everything needed to
generate its own documentation — the `.intent/` constitution, the ADR
log, the audit finding history, the consequence chain, the capability
map. Documentation generation is a natural CORE workflow, not an
external tool.

**Open questions:**
- Which documents are generated on every release vs. on demand?
- Is the API reference auto-generated from FastAPI's OpenAPI output,
  or hand-curated?
- Does the Compliance Evidence Package require a human-signed cover
  page (governor attestation)?
- What is the output format for GxP — PDF, structured HTML, or both?

**ADR trigger:** Documentation architecture ADR; likely a CORE workflow
(a Will-layer job that produces documentation artifacts on release).

---

## Track 5 — Licensing & Entitlement

**What it is:** The commercial and legal mechanism that governs who can
run CORE, under what terms, and at which capability tier.

**Tier model (existing, from product strategy):**

| Tier | Target | Key capabilities |
|------|--------|-----------------|
| CORE Audit | Free / evaluation | Read-only audit, no autonomous remediation |
| Solo | Single governor, local | Full A3 autonomy, single project |
| Team | Multi-operator, server | RBAC, shared governance, multi-project |
| Enterprise | Regulated industries | GxP compliance package, SLA, support |
| Embedded | OEM / platform vendors | White-label, API-only, custom constitution |

**Components:**
- License file format and validation (offline-capable for air-gapped)
- Feature gates per tier (what is locked vs. unlocked)
- Entitlement check in daemon startup and API layer
- Trial / evaluation mode
- Belgian incorporation implications (GDPR, B2B contract law)

**Open questions:**
- Is license validation fully offline (required for air-gapped GxP)?
- What is the enforcement mechanism — honor system, license key, or
  cryptographic entitlement token?
- Does Embedded tier require a separate IP agreement?
- What happens when a license expires — graceful degradation or hard
  stop?

**ADR trigger:** Licensing architecture ADR; requires Belgian legal
counsel input on contract structure.

---

## Track 6 — Security Hardening

**What it is:** The set of security properties CORE must demonstrate
before any multi-user or internet-facing deployment.

**Components:**
- TLS for all API communication (mandatory for multi-operator model)
- Secrets management — no credentials in config files, `.env`, or
  committed YAML; integration with a secrets store (Vault, env injection)
- Dependency vulnerability scanning — `pip-audit` already in quality
  gates; must be part of release pipeline
- No customer code transiting external servers — architectural guarantee
  must be contractual (data residency clause)
- Input validation — all API inputs validated at schema layer (Pydantic
  v2 already in ADR-053 D3)
- Rate limiting — for multi-operator and CI-embedded models
- Penetration testing — before Enterprise tier goes live

**Open questions:**
- Is the data residency guarantee enforced architecturally (no outbound
  calls to non-local LLM) or contractually only?
- What secrets store is supported for v1 Enterprise — environment
  variables only, or Vault / AWS Secrets Manager?
- Is pen testing in-house or third-party?

**ADR trigger:** Security posture ADR before any public-facing deployment.

---

## Track 7 — Compliance Evidence Package (GxP / EU AI Act)

**What it is:** The documentation and audit trail artifacts that allow
a regulated-industry customer (GxP early adopter (pharma, Belgium) archetype) to use CORE's output as
evidence in a GxP or EU AI Act compliance context.

**Regulatory anchors:**
- EU AI Act Articles 9 (risk management) and 17 (quality management)
- GxP Annex 11 (computerised systems in pharmaceutical manufacturing)
- 21 CFR Part 11 (electronic records and signatures, US equivalent)

**Components:**
- IQ (Installation Qualification) — evidence that CORE is installed
  correctly per specification
- OQ (Operational Qualification) — evidence that CORE behaves as
  specified under defined conditions
- PQ (Performance Qualification) — evidence that CORE performs
  correctly in the customer's specific environment
- Change control record — every ADR is a change control document;
  the ADR log is the change control register
- Audit trail export — `core.audit_findings` + consequence chain in
  regulator-readable format (PDF or structured XML)
- Electronic signature model for proposal approvals — ADR-053 D7
  `requested_by` attribution is the foundation; formal e-signature
  may be required for some GxP contexts
- Predicate risk classification — is CORE a GxP-critical system or
  a supporting tool? (determines validation depth required)

**Open questions:**
- Who validates CORE for GxP early adopter (pharma, Belgium)'s company — CORE (us) or GxP early adopter (pharma, Belgium)'s validation
  team using our IQ/OQ/PQ templates?
- Is predicate risk classification provided by CORE or determined
  per-customer?
- Does 21 CFR Part 11 apply (US pharma) or Annex 11 only (EU)?
- What is the audit trail export format acceptable to Belgian/EU
  regulatory inspectors?

**ADR trigger:** GxP compliance architecture ADR; requires input from
a GxP consultant (GxP early adopter (pharma, Belgium) or equivalent). This is the highest-value
near-term track for the EIC Accelerator application.

---

## Track 8 — Observability & Incident Response

**What it is:** The operational instrumentation and response procedures
that allow an IT team (not just the governor) to operate CORE in
production.

**Components:**
- External monitoring — uptime probe, daemon health endpoint, alerting
  (Prometheus metrics, or simpler for v1)
- SLA definition — what uptime and response-time guarantees does CORE
  offer per tier
- Runbook — what an operator does when the daemon crashes, DB is
  unreachable, or a proposal executes incorrectly
- Backup & recovery — DB backup cadence, tested restore procedure,
  RTO/RPO targets per tier
- Incident classification — severity levels, escalation path, governor
  notification

**Open questions:**
- Is Prometheus the target metrics format, or is a simpler health
  endpoint sufficient for v1?
- What is the RTO/RPO target for Enterprise tier?
- Does CORE offer managed hosting (SaaS), or is it always
  customer-hosted? (Determines who owns the runbook.)

**ADR trigger:** Observability ADR; can be deferred until first
Enterprise customer is in procurement.

---

## Track 9 — Onboarding

**What it is:** The path from zero to productive for a new governor or
operator, including documentation, tooling, and support touchpoints.

**Components:**
- Getting Started guide — first audit, first proposal approval, first
  autonomous fix, in under 60 minutes
- `.intent/` scaffold generator — a new project should not start from
  a blank constitution
- Interactive onboarding wizard (CLI or web UI) — guided first-run
- Example project — a reference codebase with known violations that
  demonstrates CORE's full loop end-to-end
- Video walkthrough (optional but high-conversion for regulated-industry
  buyers who need to see before they buy)

**Open questions:**
- Is the example project a public GitHub repo or a private template?
- Does the scaffold generator produce a minimal or full `.intent/`?
- Is onboarding self-serve for Solo tier, or guided for Enterprise?

**ADR trigger:** Onboarding architecture ADR; low urgency until first
external customer is in evaluation.

---

## Sequencing Recommendation (architect's view)

Not binding — governor sets sequence. Offered as input.

**Near-term (enables EIC Accelerator application and GxP early adopter (pharma, Belgium) evaluation):**
1. Track 7 — GxP compliance architecture ADR (highest commercial value)
2. Track 1 — Operating model inventory (prerequisite for Track 7 IQ/OQ)
3. Track 3 — Auth model ADR (prerequisite for multi-operator model)

**Mid-term (enables Enterprise tier):**
4. Track 2 — Installation & upgrade
5. Track 6 — Security hardening
6. Track 4 — Documentation automation

**Later (at first paying Enterprise customer):**
7. Track 5 — Licensing & entitlement
8. Track 8 — Observability & incident response
9. Track 9 — Onboarding

---

## References

- `.specs/decisions/ADR-053-api-governance-interface.md` — API protocol
  contract; D7 request attribution is the foundation for Tracks 3 and 7.
- `.specs/decisions/ADR-050-cli-positioning.md` — operating model
  topology; CLI→API→CORE is the model all tracks build on.
- `CORE-Mind-Body-Will-Separation.md` — architectural boundary; data
  residency guarantee (Track 6) derives from this.
- EIC Accelerator framing — EU AI Act Articles 9/17 (Track 7) is the
  primary regulatory hook for the application.
- Product tier strategy (existing, in governor planning notes) —
  Audit / Solo / Team / Enterprise / Embedded tiers (Track 5).
- GxP early adopter (pharma, Belgium) (GxP contractor archetype, Belgium) — primary early-adopter for Tracks 7 and 3.

## Track 10 — Documentation Governance Alignment

**What it is:** Classification and remediation of all CORE documentation
against a three-tier taxonomy. This is not writing cleanup — it is
governance positioning, constitutional boundary clarification,
externalization readiness, and narrative architecture.

**Why it is a Band E track:** External credibility for EIC, regulated-
industry buyers, enterprise architects, and serious technical evaluators
depends on the documentation register matching the maturity of the
system itself. Older identity-forming papers that carry first-person
framing, moral absolutism, or founder-sovereignty language actively
undermine the operational and governance material that already reads at
enterprise grade.

**The three-tier taxonomy:**

| Tier | Description | Location | Tone |
|------|-------------|----------|------|
| A — Public / Enterprise Canonical | README, ADRs, architecture papers, investor material, governance specs | `.specs/decisions/`, `.specs/papers/`, root | Impersonal, system-centric, evidence-oriented, technically defensible |
| B — Founder Essays / Vision Papers | Philosophical material, origin rationale, intellectual positioning | `.specs/essays/` or `.specs/vision/` (new) | Authentic, first-person acceptable, clearly labelled as founder perspective |
| C — Internal Constitutional Specifications | RFCs, governance protocols, compliance artifacts | `.intent/` | RFC-style, derivation-based, authority-explicit, failure-mode-aware |

**Category A style constraints (binding for all Tier A documents):**

- No first-person singular (`I`, `me`, `my`)
- No emotional or moral absolutism (`dangerous`, `truth`, `honest`,
  `fatal`, `non-negotiable` used as rhetorical intensifiers)
- No unverifiable claims
- No governance-centralization language (`only by me`, `solely at my
  discretion`)
- Prefer system-centric language over founder-centric language
- Prefer operational terminology over ideological framing
- All assertions must be technically defensible or explicitly marked
  as design intent

These constraints are standing policy, not a one-time rewrite target.
Without explicit constraints, the problem recurs incrementally as new
documents are authored.

**Remediation target:** The older "identity-forming" papers — primarily
the North Star paper and any positioning document predating ADR-040.
The ADRs, planning documents, and Band E tracks are already in the
correct register and require no remediation.

**Key action — "only by me" removal:** This phrase, wherever it appears
in Tier A or Tier C documents, must be replaced before any external
distribution. Suggested replacement:

> "CORE constitutional artifacts are version-governed and intentionally
> controlled to preserve governance integrity and prevent unauthorized
> constitutional drift."

Same technical meaning. No governance-centralization signal.

**Philosophical material is not deleted — it is relocated.** Documents
containing the founder's intellectual origin and differentiation argument
are moved to `.specs/essays/` or `.specs/vision/`, clearly labelled as
founder perspective. This separation strengthens both layers: the
technical artifacts stop competing with the philosophy; the philosophy
stops being read as constitutional law.

**Open questions:**
- Who classifies ambiguous documents — governor alone, or with architect
  input?
- Is `.specs/essays/` public (GitHub-visible) or private?
- Does the Category A style constraint require a linting rule
  (`regex_gate` on forbidden phrases in Tier A paths)?

**ADR trigger:** Documentation Governance Alignment ADR — defines the
taxonomy formally, lists the remediation targets by document, and
establishes the Category A style constraint as a constitutional rule.
A `regex_gate` enforcing Category A constraints on `.specs/decisions/`
and `.specs/papers/` is the natural enforcement mechanism.

**Status (2026-05-24):** Two ADRs collectively address this track —
**ADR-065 (Documentation layer separation: `.specs/` vs `docs/`)** 2026-05-20
declares the placement law (governance layer vs communication layer,
one-way authority `docs/` → `.specs/`, placement rules per audience),
and **ADR-068 D6** 2026-05-22 provides the canonical replacement template
for founder-sovereignty language in Tier A documents (resolves the
"only by me" remediation with a derivable substitution rather than an
editorial judgment call). The remaining open work in this track —
authoring a regex_gate for the Category A style constraint, and the
mechanical remediation pass across older identity-forming papers —
is no longer blocked on the taxonomy decision.

**Status (2026-07-06):** First document remediated. `CORE-USER-REQUIREMENTS.md`
relocated from `.specs/northstar/` to `.specs/essays/CORE-USER-REQUIREMENTS-founder-vision.md`
(founder's vision classification; editorial note added; §2 framing updated to
system-centric language; northstar original replaced with redirect stub). This
is the first Tier B relocation under the Track 10 taxonomy. The `regex_gate`
enforcement rule and the broader remediation pass across remaining older papers
remain open.
