---
kind: adr
id: ADR-124
title: 'ADR-124 — CORE OSS trusted-localhost mode: no UAC in the runtime'
status: accepted
---

<!-- path: .specs/decisions/ADR-124-user-access-control.md -->

# ADR-124 — CORE OSS trusted-localhost mode: no UAC in the runtime

**Status:** Accepted — superseded commercial UAC blueprint extracted to downstream distributions (2026-07-05)
**Date:** 2026-06-10 (original); updated 2026-07-05
**Governing paper:** `.specs/papers/CORE-Deliberate-Non-Goals.md`

---

## Decision

CORE is an auth-free OSS runtime. It binds to `127.0.0.1:8000` and operates in
**trusted-localhost mode** — no authentication, no session management, no
multi-tenant user access control.

`src/api/dependencies.py` exposes `require_governor` and `require_operator` as
no-op pass-throughs (`Depends(_oss_passthrough)`). These are extension seams:
downstream distributions mount real role guards on top without modifying CORE.

Multi-tenant UAC (users, organisations, roles, invitations, API keys, JWT tokens,
email delivery) lives in downstream distributions, not in this repository.

## Consequences

- No `auth_routes.py` in `src/api/v1/`.
- No JWT secret, session store, or auth middleware in CORE.
- No `core-admin auth login/logout/whoami` commands — these commands belong in
  downstream tooling that knows about users and sessions.
- The `require_governor` seam is available for downstream distributions to
  replace with a real guard at mount time.
