# CORE — BYOR / GRC Program — Open Threads

**Status:** Working backlog (derived, non-authoritative)
**Location:** `.specs/planning/CORE-BYOR-Program-Backlog.md`
**Audience:** Internal — engineering sequencing for the BYOR adoption surface + the GRC commercial wedge
**Created:** 2026-06-17

---

## 0. How to read this

Derived backlog for the BYOR/GRC program. The *shape* is set by `CORE-BYOR.md`
(paper); decisions land as ADRs grounded in it; ship-state is the issues/ADRs
themselves. This doc only sequences what is open after the 2026-06-17 session
that parametrized the obligation layer and ratified + implemented ADR-111.

---

## 1. Done 2026-06-17 (context)

- **Obligation layer parametrized** (`57379c9d`) — code is artifact type #1, not
  CORE's scope; Final Invariant generalized ("never produce *work* it cannot defend").
- **`CORE-BYOR.md`** (paper, draft) — domain-general adoption surface; "Repository"
  is the single parametrization seam; two maturity axes (Autonomy × Reach); GRC
  gap-analysis as the first paid wedge under an honesty guardrail.
- **ADR-111** (accepted) + implemented (`d0418920`) — `project onboard` *delivers*
  the authored starter (machinery floor + 4-rule constitution) into `<target>/.intent/`;
  generator path removed. **#640 step 1 closed**, verified end-to-end.

---

## 1b. Done 2026-06-20

- **T1 closed** — consumer-mode enforcement verified (see T1 above). Bug B fixed
  (`action_risk.yaml` in starter). T2 unblocked.
- **ADR-119 (Scout) accepted** — BYOR Path 1 renamed Scout; two-phase delivery
  model: `project onboard` (machinery floor) + `project scout` (LLM induction +
  human ratification). Four BYOR path codenames: Scout / Guard / Counsel /
  Generate (sibling). T3 scope corrected to machinery floor only. ADR-108 D1 and
  ADR-111 D1 amended. CORE-BYOR.md §4 table and §8/§9 updated.
- **T5e closed** — ADR-118 fully implemented: `RequirementVerdict` contract (`ae36aa6f`
  D1/D3/D4/D5) + applicability gate detect→suggest→confirm (`1587ebad` D2). Engine
  reshaped to corpus-level verdict unit; silence ≠ verdict; `not_covered` /
  `covered_unauthoritatively` / `not_applicable` / `unavailable` first-class.

## 1c. Done 2026-06-21

- **T5a closed** — ADR-120 accepted + implemented (`a9b19264`): `DocumentRepository`
  adapter interface + `RepositoryAdapterBase` abstract contract (F-41/F-42/F-43
  binding). The seam that decouples domain-specific corpus reading from the engine.
- **T5b closed** — ADR-121 accepted + implemented (`a9b19264`): `document_corpus`
  artifact type, `document_corpus_sensor` worker, `document.run.gap_analysis` action.
  Domain-agnostic rename: `GRCGapAnalysisService` → `DocumentCorpusAnalysisService`
  (alias kept). Pre-existing cross-validation bug in `intent_repository` fixed (identity
  nesting). 7 tests authored, tree clean.
- **T5c closed** — ADR-113 fully implemented: `EvidenceClass` enum (PROVEN/JUDGED/ATTESTED)
  + field on `AuditFinding` (D1); derived from `BaseEngine.evidence_class` class var,
  stamped in `rule_executor` (D2); fail-closed to ATTESTED (D3); `attestation_gate`
  engine surfaces "ATTESTATION REQUIRED" (D4); orthogonal to severity (D5); general
  — code audit + GRC both label findings (D6). All 16 registered engines carry an
  explicit declaration; registry-sweep test enforces this going forward. Surfaces in
  CLI via `check/formatters.py` and `grc/gap_analysis.py`.

## 1e. Done 2026-06-22 (SaaS delivery — T6a/T6b/T6c)

- **ADR-125 accepted + implemented** (`6b577d66`) — Full SPA frontend scaffold: Vite 8,
  React 19, TypeScript 6, Tailwind v4, shadcn/ui, TanStack Router v1 (file-based routing),
  TanStack Query v5, Orval v8 (typed API client generated from OpenAPI). Single-flight
  refresh mutator (`fetch-client.ts`). Makefile targets: `web-install`, `web-dev`,
  `web-build`, `web-generate-schema`, `web-generate-api`. FastAPI serves `web/dist/` via
  `/{full_path:path}` catch-all (ADR-125 D11); SPA active only when `web/dist/` exists.
- **T6a closed** (`c0d7dbda`) — Auth screens: login, register, forgot-password,
  reset-password. TanStack Router pathless layout routes (`_public` for auth,
  `_app` for protected). `beforeLoad` guard on `_app.tsx` redirects to `/login` on 401.
  Dashboard stub with user email + sign-out. Password min 12 chars; no-leak pattern on
  forgot-password.
- **T6b closed** (`c0d7dbda`) — CORS narrowed from `["*"]` to `settings.CORS_ORIGINS`
  (default `["http://localhost:5173"]`; JSON env var override in prod). `CORS_ORIGINS`
  field added to `src/shared/config.py`.
- **T6c closed** (`4e1a199f`) — All `/v1/` routes gated with `Depends(get_current_user)`
  via intermediate `APIRouter(prefix="/v1", dependencies=[...])`. Option 1 (blanket gate);
  migration to per-route role checks (Option 2) is ~25 lines. `/health` and `/auth/*`
  remain public. Verified: unauthenticated POST `/v1/audit/runs` → 401.

---

## 1d. Done 2026-06-21 (UAC / SaaS foundation)

- **ADR-124 accepted + implemented** (`4c961772`) — User Access Control foundation for SaaS
  delivery. Full auth stack: bcrypt password hashing (passlib, cost 12), JWT access tokens
  (1 hr, HS256, httpOnly cookie), opaque refresh tokens (30 d, SHA-256 stored), 5-role model
  (VISITOR/ANALYST/AUDITOR/ORG_ADMIN/PLATFORM_ADMIN), org + org_membership tables, invitation
  flow, API key management, audit event log. 14 REST endpoints under `/auth/` registered in
  core-api. Transactional email via Resend (graceful dev-mode degradation — tokens returned
  in response when `RESEND_API_KEY` absent). In-process sliding-window rate limiting on
  login/register/password-reset. `get_current_user` + `require_role` FastAPI dependency
  providers in `api/dependencies.py`. 10 unit tests for password + token primitives.
  DB schema applied to 192.168.20.23/core.
- **DB additions** — 2 ENUMs (`core.auth_method`, `core.user_role`), 8 tables:
  `core.users`, `core.organisations`, `core.org_memberships`, `core.refresh_tokens`,
  `core.password_reset_tokens`, `core.invitations`, `core.api_keys`, `core.auth_events`.
- **Config additions** — `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`,
  `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `RESEND_API_KEY`, `APP_BASE_URL` in
  `src/shared/config.py` and `.env`.

---

## 2. Open threads

### T1 — Verify consumer-mode enforcement  **[DONE — 2026-06-20]**
Confirmed. `code audit --offline` from inside a consumer repo enforces all four
starter rules: 5 blocking + 8 reporting findings, verdict FAIL on planted
violations. Root cause (Bug B): `assisted.apply_diff` / `assisted.validate_diff`
absent from starter's `action_risk.yaml`; fix applied to
`examples/starter-intent/.intent/enforcement/config/action_risk.yaml` and
committed. T2 unblocked.

### T2 — #640 step 2: newcomer docs  **[DONE — 2026-06-20]**
Three surfaces updated in `5f15ded7`: `docs/cold-reviewer.md` dead-end replaced with
`project onboard` + `project scout` instructions; `getting-started.md` BYOR table row +
callout added; `README.md` Quick Start callout updated. `pip install` users caveated
until #674 lands (T3).

### T3 — #674: ADR-108 D3 machinery-in-wheel  **[SCOPE CORRECTED — ADR-119 D9]**
Bundle the **machinery floor only** in the `core-runtime` wheel + loader fallback
so `pip install` adopters can run `project onboard` (Phase A), not only source-tree
runs. The rules layer is never bundled — it is per-repo-inducted by `project scout`
or per-repo-authored; there is no canonical rule set to ship. Unblocks wheel-user
BYOR Phase A. Tracked: issue #674.

### T4 — `work/`-staging airlock for onboard  **[DONE — 2026-06-21]**
ADR-123 accepted + implemented. `--stage` flag on `project onboard` redirects writes to
`work/staged/<name>/`. `project onboard promote <path>` completes delivery and cleans up
the stage dir. Direct-write path (`--write` without `--stage`) unchanged.

### T5 — BYOR-grounded ADRs (`CORE-BYOR.md` §9)

- **T5a** ✅ **DONE 2026-06-21** — Repository adapter interface (ADR-120, `a9b19264`).
- **T5b** ✅ **DONE 2026-06-21** — GRC `document_corpus` type (ADR-121, `a9b19264`).
  Includes `document_corpus_sensor` + `document.run.gap_analysis` action.
  Regulation→Intent residency boundary decided in ADR-116 (catalog as data; `public/`,
  `licensed/`, `internal/` tiers). Domain-agnostic: any document corpus, not GRC-only.
- **T5c** ✅ **DONE 2026-06-21** — Per-finding attestation (ADR-113). All 6 decisions
  shipped; 16 engines declared; registry-sweep test enforces completeness going forward.
- **T5d** ✅ **DONE 2026-06-21** — GRC internal audit corpus pipeline (ADR-122,
  ADR-116 D9). `core-admin grc ingest <framework_id>`: licence gate → chunk → embed →
  Qdrant upsert (`grc-internal-{framework_id}`) → provenance write. `grc_judge`
  augmented with top-3 passage injection (degrades gracefully on absent collection;
  `EvidenceClass` stays JUDGED). `framework_id` injected into `grc_judge` params by
  `load_catalog`. Copyrighted frameworks (iso_27001/gamp5/cyfun) remain procurement-gated;
  ungated frameworks (nist_800_171/gdpr/cfr_part_11/eu_annex_11) can be ingested now.
- **T5e** ✅ **DONE 2026-06-20** — Verdict unit: requirement-over-corpus (ADR-118,
  `ae36aa6f` D1/D3/D4/D5 + `1587ebad` D2). `RequirementVerdict` + applicability gate.
  (See §1b above.)

### T6 — SaaS delivery: remaining auth surfaces  **[PARTIAL — T6a/T6b/T6c done]**

Auth backend live. Frontend + auth gate shipped. Remaining before external users can log in:

- **T6a** ✅ **DONE 2026-06-22** — Auth screens (login/register/forgot/reset) + SPA scaffold
  (ADR-125). Commits `6b577d66` + `c0d7dbda`.
- **T6b** ✅ **DONE 2026-06-22** — CORS narrowed to `settings.CORS_ORIGINS` (`c0d7dbda`).
- **T6c** ✅ **DONE 2026-06-22** — All `/v1/` routes gated; `/health` + `/auth/*` public
  (`4e1a199f`).
- **T6d — Resend setup** — set `RESEND_API_KEY` and `APP_BASE_URL` in `.env` (and
  `APP_DOMAIN` in Resend dashboard) when a Resend account is provisioned. Dev mode already
  returns tokens in JSON response as fallback.
- **T6e — Google OAuth** — stub column (`auth_method`) already in `core.users`. Needs:
  Google Cloud project, OAuth 2.0 credentials, `authlib` or `httpx-oauth` flow,
  `/auth/google` + `/auth/google/callback` routes. Separate ADR recommended.
- **T6f — MFA (v2)** — `mfa_secret` column already in `core.users`. TOTP via `pyotp`.
  Separate ADR. No urgency until T6a–T6d are operational.

---

## 3. Sequencing

**As of 2026-06-22:** T1/T2/T3/T4/T5a/T5b/T5c/T5d/T5e (BYOR program) + UAC foundation
(ADR-124) + SaaS delivery T6a/T6b/T6c are all shipped.

Remaining operator actions:
- **T5d procurement** — iso_27001/gamp5/cyfun require a commercial licence before
  `core-admin grc ingest` will run. Engineering done; blocker is procurement.
- **T6d** — operator config: set `RESEND_API_KEY` + `APP_BASE_URL` in `.env`.
- **T6e/T6f** — v2 (Google OAuth, MFA). Separate ADRs; no urgency until T6d is live.

The commercial center of gravity is GRC (governor decision 2026-06-17). Code
self-development runs on a maintenance track. SaaS delivery (T6) is the next engineering
epoch.

---

## 4. References

- `CORE-BYOR.md` — the program's shape (grounds the ADRs below)
- ADR-111 — `project onboard` delivers the authored starter (#640 step 1)
- ADR-116 (D7 inventory registry, D8 tier=repo boundary, D9 internal audit corpus → T5d)
- ADR-118 (GRC verdict unit: requirement-over-corpus + applicability gate → T5e ✅)
- ADR-119 (Scout — BYOR Path 1 induction ✅)
- ADR-120 (repository adapter interface — T5a ✅)
- ADR-121 (document_corpus type — T5b ✅)
- ADR-108 (D3 → #674 → T3)
- ADR-075 (namespace), ADR-090 (multi-domain)
- ADR-124 (user access control — UAC foundation, T6 precursor ✅)
- ADR-125 (web/ SPA frontend scaffold — T6a ✅)
- #640 (BYOR newcomer docs — T2), #674 (wheel packaging — T3)
