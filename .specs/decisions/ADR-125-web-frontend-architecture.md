---
kind: adr
id: ADR-125
title: 'ADR-125 — CORE OSS has no web frontend'
status: accepted
---

<!-- path: .specs/decisions/ADR-125-web-frontend-architecture.md -->

# ADR-125 — CORE OSS has no web frontend

**Status:** Accepted — web frontend extracted to downstream distributions (2026-07-05)
**Date:** 2026-06-10 (original); updated 2026-07-05
**Governing paper:** `.specs/papers/CORE-Deliberate-Non-Goals.md`

---

## Decision

CORE is a CLI-and-API runtime. It has no web frontend, no SPA serving, and no
browser-facing UI in this repository.

The `src/api/main.py` entry point mounts `/v1` runtime routers and `/health` only.
It does not serve `web/dist/` and has no SPA catch-all route.

Browser-based governance interfaces (convergence dashboards, proposal UIs, GRC
audit state views) belong in downstream distributions that consume the CORE API
surface (ADR-087) and build their own frontend on top.

## Consequences

- No `web/` directory in CORE.
- No `StaticFiles`, `HTMLResponse`, or SPA catch-all in `src/api/main.py`.
- No frontend build pipeline in this repo.
- Downstream distributions own their frontend stack entirely.
