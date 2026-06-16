# CORE — Maturity-Audit Action List

**Status:** Working backlog (derived, non-authoritative)
**Location:** `.specs/planning/CORE-Maturity-Audit-Actions.md`
**Audience:** Internal — engineering sequencing input
**Created:** 2026-06-16
**Source:** External artifact-based maturity audit (2026-06-16). The audit did **not**
clone the repo, run `install-core.sh`, run tests, or read CI logs / `.intent/` rules —
it read public GitHub artifacts only. Treat every item as a **lead to verify**, not a
confirmed gap.

---

## 0. How to read this

This is a **derived** backlog. It does not govern sequencing. The authoritative
operational surface is [`CORE-Operational-Completeness.md`](CORE-Operational-Completeness.md)
(ADR-085); when an item here overlaps that tracker, **the tracker wins** and this doc
just points at it.

Two filters were applied to the raw audit before writing this list (per
`user_prefers_real_debt_over_open_count`):

1. **Staleness** — the audit is artifact-only and external, so it cannot see work
   already shipped. Items it flags that are already closed/tracked are marked
   ⚠️ **VERIFY-STALE** with the likely-superseding artifact.
2. **Rubric reframe** — two findings score CORE against an enterprise-SaaS rubric it has
   deliberately deferred (ADR-085 sequencing). Those are reframed, not taken at face value.

Before spending effort on any item, confirm the gap is real against the repo. Do not
trust the audit's read.

---

## 1. P1 — Adoption blocker (verify first, likely real)

- [ ] **Fix BYOR onboarding (#640).** `project onboard` reads a missing
  `starter_kits/default/` path → fails at runtime. Ship a minimal valid `.intent/`
  scaffold so an external repo can be governed without hand-authoring the constitution.
  *This is the audit's single most load-bearing finding and aligns with the open
  external-adoption gap. Verify #640 is still open before starting.*
- [ ] **Fail-fast on a no-`.intent/` repo.** Auditing a repo with no constitution
  currently hangs instead of erroring with guidance. Exit with an actionable message
  ("run `project onboard` first"). *Same root surface as #640.*

---

## 2. P2 — Proof → enforcement (highest leverage, in CORE's own idiom)

- [ ] **Convert each Proof Index row into a CI-enforced regression check** where
  mechanizable. A proof claim with no standing check is exactly the rot pattern CORE
  exists to prevent (`feedback_closed_by_adr_not_evidence`).
- [ ] For rows that cannot be mechanized yet, mark them **attestation-only** so the gap
  is visible rather than implied-covered. Relates to `CORE-Instrument-Attestation`.

---

## 3. P3 — CI assurance (smoke → tiered)

> ⚠️ **VERIFY-STALE boundary:** the **F-10 CI/CD gate shipped 2026-06-02** (the GitHub
> Action runs `core-admin code audit --offline` against external repos with
> merge-blocking annotations). What's below is the **internal CI** for the CORE repo
> itself, which the audit correctly observed is still smoke-only (`pytest -q`). These
> are distinct surfaces — do not conflate with F-10.

- [ ] Add a **full test tier** beyond the `pytest -q` smoke job.
- [ ] Add an **offline constitutional audit** job (`core-admin code audit --offline`) as
  an internal CI gate.
- [ ] Add **package build + `pip install` test** (catches published-wheel-vs-source
  drift — `feedback_verify_cli_against_published_wheel`).
- [ ] Add a **GitHub Action self-test** — run `action.yml` against CORE itself.
- [ ] Add a **containerized demo / `install-core.sh` dry-run** test.
  ⚠️ **VERIFY-STALE:** demo reliability (#562) was closed **met 2026-06-14** via the
  Proxmox cold-room (4 clean / 0 fail). Confirm what's left here is the *CI-automated*
  version of that manual cold-room proof, not a re-do.
- [ ] Wire **Bandit + pip-audit** into CI (declared as deps in `pyproject.toml`, not
  gated). Note these already exist as advisory constitutional rules
  (`quality.security_audit`); this is about the *CI* surface.
- [ ] **Reframe — coverage `--cov-fail-under=45`:** the audit reads this as a "low quality
  bar." It may instead be a deliberate ramp (`feedback_ramp_arc_three_phase_pattern`,
  `user_prefers_visibility_over_polish`). Action is **document the ratchet plan**, not
  "raise the number now."
- [ ] Decide whether internal CI needs a **non-zero-exit lint tier** — pre-commit uses
  `ruff --fix --exit-zero` (good ergonomics, not a blocking gate).

---

## 4. P4 — Security governance (cheap, likely real)

- [ ] **Add `SECURITY.md`:** supported versions, vulnerability-reporting process,
  disclosure contact, secret-handling expectations, production-hardening warning, known
  security boundaries. *Verify absence first — the audit could not find one.*
- [ ] **Mark demo credentials dev-only.** Docker/Postgres demo creds + default-port
  Qdrant need an explicit "development only" boundary and a production profile.
- [ ] **Reframe — security posture vs document surface:** the audit scored security 2.5
  largely on *doc absence*. For a system whose substance is enforcement / provenance /
  audit-chain, the constitution itself is a security control surface the artifact method
  can't see. Action is a one-page **"where security enforcement actually lives"** legibility
  doc (`feedback_external_review_false_positive_is_legibility_map`), not assuming the
  posture is weak.

---

## 5. P5 — Release / interface stability

- [ ] **Reframe / VERIFY-STALE — public API boundary:** the audit calls this "pending,"
  but **F-48.4 (public-vs-internal API) shipped 2026-06-02** and **F-40 / ADR-087**
  authored the OEM API stability policy with a published OpenAPI contract
  (`contracts/oem_api_v1.openapi.json`). Verify against those before treating it as open;
  the real residual is likely *promotion criteria from Beta → stable*, not the boundary
  itself. See [`CORE-Semver-Policy.md`](CORE-Semver-Policy.md).
- [ ] Keep PyPI status honest (Beta) until any remaining promotion criteria land.

---

## 6. P6 — Operational completeness

- [ ] Define a **production deployment profile** (audited artifacts show local-runtime
  only). *Check this isn't already covered under the ADR-085 operational tracker.*
- [ ] Document **production secret-management** beyond `.env.example`.

---

## 7. What this list is NOT

- It is **not** a re-scoping of ADR-085's 5+3 list. New items here that warrant
  engineering capacity under the active constraint must route through the
  operational-completeness tracker / governance, not this doc.
- It is **not** confirmed debt. Every box is a lead from an external artifact audit;
  several are likely stale (the audit can't see shipped work). Verify before acting.
- The composite "3.6 / 5" score from the source audit is intentionally omitted — an
  unweighted average across heterogeneous axes discards the only signal that matters
  (which axis is weak and why).

---

## 8. References

- [`CORE-Operational-Completeness.md`](CORE-Operational-Completeness.md) — authoritative
  ADR-085 tracker (overlapping items defer to it)
- [`CORE-Semver-Policy.md`](CORE-Semver-Policy.md) — release / version policy
- ADR-085 — operational-completeness constraint
- ADR-087 — OEM API stability policy
- #640 — BYOR onboarding defect (P1)
