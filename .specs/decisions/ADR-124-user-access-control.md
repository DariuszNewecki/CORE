---
kind: adr
id: ADR-124
title: 'ADR-124 — User Access Control (UAC)'
status: accepted
---

# ADR-124 — User Access Control (UAC)

**Status:** accepted
**Date:** 2026-06-21
**Deciders:** Governor

---

## Context

CORE is moving toward a SaaS delivery model. The GRC product is the commercial wedge and
external customers are imminent. Currently CORE has no user model: every operation runs as
the OS process with no identity, attribution, or access boundary. Before any external user
touches the system, a foundational UAC layer must exist.

Requirements driving this ADR:

- A user visits a URL, gets a login/register screen, authenticates, and accesses CORE
  functionality scoped to their organisation and role.
- Self-registration must be supported (invite-only is not acceptable as the sole path).
- Invitation links are also supported as a second entry path (pre-assigns role, skips VISITOR
  holding state).
- New registrants default to VISITOR — no functional access until promoted.
- The governor (PLATFORM_ADMIN) and org-level admins (ORG_ADMIN) control promotion.
- The web frontend is being built separately; this ADR governs the API layer, DB model, and
  auth mechanics only.

---

## Decisions

### D1 — User model

A `users` table with the following fields:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | text UNIQUE NOT NULL | verified address |
| `password_hash` | text NULLABLE | null for OAuth-only accounts |
| `auth_method` | enum(`email`, `google`) | |
| `email_verified` | bool DEFAULT false | gate on activation |
| `is_active` | bool DEFAULT true | suspension flag |
| `mfa_secret` | text NULLABLE | TOTP seed; null until MFA enrolled (v2) |
| `created_at` | timestamptz | |
| `last_login_at` | timestamptz NULLABLE | |

Email verification is required before VISITOR status activates. Unverified accounts have no
access to any route.

### D2 — Organisation model

A `organisations` table:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | text UNIQUE NOT NULL | collision-safe; case-insensitive unique |
| `slug` | text UNIQUE NOT NULL | URL-safe identifier |
| `created_at` | timestamptz | |
| `created_by` | UUID FK → users | founding ORG_ADMIN |

**Org creation on self-register:** the registration form accepts an optional `organisation_name`.
If supplied and the name does not exist, the org is created and the registrant becomes
ORG_ADMIN. If the name already exists (case-insensitive match), the registrant joins as
VISITOR pending ORG_ADMIN approval — no duplicate org is created. If no org name is
supplied, the user is VISITOR with no org until promoted.

One user belongs to at most one organisation (multi-org membership is deferred).

**Phase 2 constraint — org-name squatting:** self-register-creates-org is acceptable for
Phase 1 (governor dogfooding; controlled registrant). It is not safe for customer-facing
deployment: the first person to type a real company name becomes its ORG_ADMIN, and
legitimate employees who self-register thereafter join as VISITORs pending that squatter's
approval. Before Phase 2 ships, the governor must choose one of two paths:

- **Domain-verified self-register:** org creation requires the registrant's email domain
  to match a pre-declared `allowed_domains` list on the org record. The column is added to
  the schema now (nullable; not enforced in Phase 1).
- **Governor-mediated creation:** PLATFORM_ADMIN creates orgs and distributes invitations;
  the self-register-creates-org path is disabled for non-PLATFORM_ADMIN registrants.

The `organisations.allowed_domains` column (`text[] NULLABLE`) is added to the schema now
so Phase 2 does not require a migration. Enforcement is deferred.

### D3 — UserGroup (role) model

Five roles, ordered by privilege:

| Role | Scope | What they can do |
|---|---|---|
| `VISITOR` | Global | Registered and email-verified; no functional access |
| `ANALYST` | Org-scoped | Run gap analyses, view reports for their org's frameworks |
| `AUDITOR` | Org-scoped | Create/manage audit projects, assign work within their org |
| `ORG_ADMIN` | Org-scoped | Manage org users; promote within their org up to AUDITOR; generate API keys |
| `PLATFORM_ADMIN` | Global | Full access; create orgs; promote anyone including to ORG_ADMIN/PLATFORM_ADMIN |

`org_memberships` join table:

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | |
| `organisation_id` | UUID FK → organisations | |
| `role` | enum (roles above) | |
| `promoted_by` | UUID FK → users NULLABLE | who granted this role |
| `promoted_at` | timestamptz NULLABLE | |
| `created_at` | timestamptz | |

VISITOR users with no org have no `org_memberships` row. PLATFORM_ADMIN is stored as a
membership row with `organisation_id = NULL` (global scope marker).

ORG_ADMIN may promote within their own org up to AUDITOR. They may not self-promote to
PLATFORM_ADMIN. PLATFORM_ADMIN promotion is governor-only.

### D4 — Authentication mechanics

**Password hashing:** argon2id with parameters (memory=64 MiB, iterations=3,
parallelism=1). Neither bcrypt nor scrypt is used. Parameters satisfy OWASP's minimum
argon2id recommendations; increase if deployment hardware is significantly more capable.

**Tokens:** short-lived JWT access token (1 hour) + long-lived refresh token (30 days).
Token transport is governed by D10 (httpOnly cookies). Refresh tokens are stored in the
`refresh_tokens` table — see schema below under *Refresh token rotation*.

**Refresh token rotation and reuse detection:** refresh tokens rotate on every use.
On a `/auth/refresh` call:

1. Look up token by hash. Not found → 401.
2. `used_at IS NOT NULL` → **reuse detected** → revoke the entire token family (all rows
   sharing `family_id`) → 401. The session is treated as compromised; the user must
   log in again.
3. `revoked = true` or `expires_at < now()` → 401.
4. Set `used_at = now()` on the current token (atomic). Insert a new token with the same
   `family_id`. Return the new token.

`refresh_tokens` schema: `(id, user_id, token_hash, family_id, used_at NULLABLE,
expires_at, revoked)`. `family_id` is a UUID generated at login and shared by every
token in a rotation chain. `used_at` is null until the token is consumed.

Reuse of an already-used token is a theft signal: the legitimate user has already
rotated past it, so only an attacker (or a replay) would present it.

**Per-account lockout:** the per-IP rate limit (D4 *Rate limiting*) is weak behind NAT
and evadable by IP rotation. The `login_failed` audit event (D7) provides the
per-account signal. After 10 consecutive `login_failed` events for the same `email`
within 15 minutes the account is locked for 15 minutes. Stored as `locked_until
timestamptz NULLABLE` on `users`. `/auth/login` checks `locked_until > now()` before
credential verification; a locked account returns 423 with a `Retry-After` header.

**Suspension immediacy:** revoking the refresh token on suspension blocks new sessions
but the existing access JWT remains valid for up to 1 hour. For a security-sensitive
suspension (compromised account) this is too long. An in-memory deny-list keyed by
`user_id` closes the gap: on suspension the user_id is added; the JWT middleware checks
the deny-list before accepting any token; deny-list entries expire at
`max(jwt_expiry, suspend_time + 1 hour)`. Implementation (Redis, Postgres-backed cache,
or in-process LRU) is deferred to implementation; the required interface is
`deny_list.is_denied(user_id: UUID) -> bool`.

**Google OAuth:** standard OAuth2 Authorization Code flow via Google. On first OAuth
login, a user record is created with `auth_method=google`, `password_hash=NULL`. Email
is taken from the Google profile and treated as verified.

**Password reset:** time-limited token (1 hour) sent to verified email. Implemented as a
`password_reset_tokens` table (id, user_id, token_hash, expires_at, used).

**Rate limiting:**

| Endpoint | Limit |
|---|---|
| `/auth/login` | 10 attempts per IP per minute |
| `/auth/register` | 10 attempts per IP per minute |
| `/auth/refresh` | 60 attempts per IP per hour |
| `/auth/password-reset/*` | 3 requests per email per hour |

Per-account lockout (above) is a separate mechanism that applies in addition to
per-IP limits, not instead of them.

### D5 — Registration and invitation flows

**Self-register path:**
1. User submits email + password (or Google OAuth).
2. Verification email sent; account created with `email_verified=false`.
3. User clicks verification link → `email_verified=true` → VISITOR access granted.
4. If org name provided: org created (ORG_ADMIN) or join-request filed (existing org).

**Invitation path:**
1. ORG_ADMIN or PLATFORM_ADMIN generates an invitation link scoped to a role and org.
2. Invitation stored in `invitations` table (id, email, org_id, role, token_hash,
   expires_at, accepted_at).
3. Recipient registers via the link → email verified immediately (link implies address
   ownership) → granted the pre-assigned role in the specified org.

Invitations expire after 7 days. A single invitation is single-use.

### D6 — API keys

ORG_ADMINs may generate API keys for programmatic/integration access within their org's
scope. API keys are stored as hashed values in an `api_keys` table (id, org_id, created_by,
key_hash, label, role, last_used_at, expires_at NULLABLE, revoked). API key auth is a
parallel path to JWT auth — the middleware accepts either.

**Role/scope:** every API key carries an explicit `role` field. Constraints:

- Permitted values: `ANALYST`, `AUDITOR`. Keys cannot be granted `ORG_ADMIN` or
  `PLATFORM_ADMIN` — service keys access data; they do not perform administrative
  operations.
- The granted role must be ≤ the creating ORG_ADMIN's highest role within the org.
- The middleware resolves API key auth to `(org_id, role)` and applies the same
  role-enforcement dependency chain as JWT auth. A key with `role=ANALYST` has
  identical access boundaries as a human ANALYST in the same org.

Implicit privilege (key inherits creator's role) is forbidden: an unscoped key that
silently acts as ORG_ADMIN is an escalation surface for any integration that is
compromised.

### D7 — Audit trail

An `auth_events` table records:

| Event type | Triggered by |
|---|---|
| `registered` | New user registration |
| `email_verified` | Email verification click |
| `login` | Successful login (email or Google) |
| `login_failed` | Failed login attempt |
| `logout` | Explicit logout |
| `token_refreshed` | Refresh token exchanged |
| `role_promoted` | User promoted to a new role |
| `account_suspended` | Account suspended |
| `account_reactivated` | Suspension lifted |
| `password_reset_requested` | Reset email sent |
| `password_reset_completed` | Password changed via reset |
| `api_key_created` | API key generated |
| `api_key_revoked` | API key revoked |
| `token_refresh_rejected` | Refresh token reuse detected; family revoked (theft signal) |
| `account_locked` | Per-account lockout triggered (failed attempt threshold reached) |
| `account_unlocked` | Lockout expired or cleared by PLATFORM_ADMIN |

Fields: id, user_id, event_type, actor_id (who triggered it — null for self-actions),
ip_address, user_agent, metadata (jsonb), created_at.

This is non-negotiable for a GRC product: customers will ask whether the platform itself
produces an access audit trail.

### D8 — MFA slot (v2)

`users.mfa_secret` is included in the schema from day one so MFA enrolment does not require
a migration. TOTP implementation (RFC 6238) is deferred to v2. The auth flow must have an
explicit hook point for the MFA check step so it is not a retrofit.

### D9 — API middleware

All routes except `/auth/register`, `/auth/login`, `/auth/verify-email`,
`/auth/refresh`, `/auth/password-reset/*`, and `/health` require a valid JWT or API key.
The middleware resolves `current_user` and `current_org_membership` and injects them into
the request context. Role checks are enforced at the route level via dependency injection,
not scattered inline.

### D10 — Token transport and browser security

Access tokens reach the browser as **httpOnly cookies**, not `Authorization` headers
and not `localStorage`. This is a one-way door: once the frontend is built against
cookies, switching transport requires rewriting the auth client.

**Cookie specifications:**

| Cookie | Name | httpOnly | Secure | SameSite | Path | Max-Age |
|--------|------|----------|--------|----------|------|---------|
| Access JWT | `core_access` | yes | yes | `Lax` | `/` | 3600 |
| Refresh token | `core_refresh` | yes | yes | `Strict` | `/auth/refresh` | 2592000 |

**Attribute rationale:**

- **httpOnly** — JavaScript cannot read or exfiltrate the token. XSS cannot steal the
  session, only make same-origin requests on the user's behalf (which httpOnly does not
  prevent, but which SameSite and short-lived access tokens bound in time).
- **Secure** — cookie is only sent over HTTPS. Mandatory in production. Dev environments
  may relax to `http://localhost`; this must never be disabled in staging or production.
- **SameSite=Lax for `core_access`** — cookie is sent on top-level GET navigations from
  external sites (needed for bookmarked/linked authenticated pages) but not on cross-site
  subresource requests (POST/PUT/DELETE). This blocks the classical CSRF vector for all
  mutating endpoints. Read-only cross-site requests that carry the cookie are benign.
- **SameSite=Strict for `core_refresh`** — the refresh endpoint is called programmatically
  (by `fetch-client.ts` on 401), never from a top-level navigation. `Strict` blocks all
  cross-site sending with no UX cost.
- **Path=/auth/refresh for `core_refresh`** — the refresh token is scoped to the one
  endpoint that consumes it. It cannot be accidentally included in API calls.

**No tokens in localStorage or sessionStorage.** These are readable by any JavaScript
on the page including injected scripts, and are the primary XSS token-theft vector.

**`fetch-client.ts` (ADR-125 D12) does not attach tokens manually.** The browser sends
`core_access` automatically on every same-origin request. The wrapper's only auth
concern is detecting 401 responses and triggering a refresh.

**CSRF residual risk and Phase 2 hardening:**

SameSite=Lax mitigates CSRF on modern browsers for mutating endpoints. Residual risk:
- Old browsers without SameSite support: negligible in 2026. A minimum-browser policy
  can be enforced at the CDN/load-balancer level for the customer-facing deployment.
- CORS misconfiguration: a permissive `allow_origins` setting would allow a malicious
  origin to make credentialed cross-site requests. The `allow_origins` tightening
  required by ADR-125 T6b is a hard pre-condition for Phase 2, not a post-launch task.
- Subdomain takeover: a compromised `*.coredomain.com` subdomain could set cookies on
  the parent domain. The `__Host-` cookie prefix (forces `Secure`, removes `Domain`,
  forces `Path=/`) eliminates this. Adoption of `__Host-` is recommended for Phase 2;
  deferred from Phase 1 because Phase 1 serves the governor on a controlled host with
  no external subdomains.

---

## Consequences

- The `users`, `organisations`, `org_memberships`, `refresh_tokens`, `invitations`,
  `api_keys`, `password_reset_tokens`, and `auth_events` tables are new schema surfaces.
  They belong in `infra/sql/db_schema_live.sql` (schema-as-truth; no migration framework).
- Schema additions beyond the original design:
  - `users.locked_until timestamptz NULLABLE` — per-account lockout.
  - `organisations.allowed_domains text[] NULLABLE` — Phase 2 domain verification; not
    enforced in Phase 1.
  - `refresh_tokens.family_id UUID NOT NULL` and `refresh_tokens.used_at timestamptz
    NULLABLE` — token rotation and reuse detection. These columns are load-bearing; the
    reuse-detection logic must not be simplified or bypassed.
  - `api_keys.role` enum NOT NULL — explicit bounded scope for every API key.
- All auth logic lives in `src/api/` (routes) and `src/body/services/auth/` (service layer).
- Password hashing uses argon2id. The parameters (memory=64 MiB, iterations=3,
  parallelism=1) are not tunable at runtime; changing them requires a decision.
- A deny-list service is required for immediate account suspension. Implementation
  (Redis, Postgres-backed cache, in-process LRU) is an infrastructure decision; the
  interface contract is `deny_list.is_denied(user_id: UUID) -> bool`.
- Access tokens travel as httpOnly cookies (`core_access`, `core_refresh`). The frontend
  does not manage token attachment; the browser does. `Authorization` header auth is not
  used for the browser client.
- The upcoming web frontend calls `/auth/*` endpoints; this ADR defines their contract.
  ADR-125 D12's `fetch-client.ts` is the browser-side counterpart; it relies on the
  cookie model specified in D10.
- Phase 2 org creation path (domain verification or governor-mediated) is a governor
  decision before Phase 2 ships. The schema column exists; the enforcement is deferred.
- Google OAuth requires a Google Cloud project + OAuth 2.0 credentials (governor action,
  out of scope here).
- Email sending (verification, password reset, invitations) requires an SMTP/transactional
  email service (governor action, out of scope here).
- MFA is designed in, implemented in v2.
- SSO/SAML for enterprise customers is deferred; the auth abstraction layer must not
  preclude it.

---

## References

- ADR-110 — Exposure trust boundary
- ADR-116 — GRC catalog residency and licensing tiers
- `CORE-BYOR.md` — SaaS delivery context
