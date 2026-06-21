# ADR-124 — User Access Control (UAC)

**Status:** Draft
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

**Tokens:** short-lived JWT access token (1 hour) + long-lived refresh token (30 days),
stored in `refresh_tokens` table (id, user_id, token_hash, expires_at, revoked). On logout
or account suspension the refresh token is revoked immediately; the access JWT expires
naturally within its window (acceptable given 1-hour ceiling).

**Google OAuth:** standard OAuth2 Authorization Code flow via Google. On first OAuth login,
a user record is created with `auth_method=google`, `password_hash=NULL`. Email is taken
from the Google profile and treated as verified.

**Password reset:** time-limited token (1 hour) sent to verified email. Implemented as a
`password_reset_tokens` table (id, user_id, token_hash, expires_at, used).

**Rate limiting:** login and register endpoints limited to 10 attempts per IP per minute.
Password reset limited to 3 requests per email per hour.

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
key_hash, label, last_used_at, expires_at NULLABLE, revoked). API key auth is a parallel
path to JWT auth — the middleware accepts either.

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

---

## Consequences

- The `users`, `organisations`, `org_memberships`, `refresh_tokens`, `invitations`,
  `api_keys`, `password_reset_tokens`, and `auth_events` tables are new schema surfaces.
  They belong in `infra/sql/db_schema_live.sql` (schema-as-truth; no migration framework).
- All auth logic lives in `src/api/` (routes) and `src/body/services/auth/` (service layer).
- The upcoming web frontend calls `/auth/*` endpoints; this ADR defines their contract.
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
