# ADR-125 — Web Frontend Architecture

**Status:** accepted
**Date:** 2026-06-21
**Deciders:** Governor

---

## Context

ADR-124 established the user identity and auth foundation for CORE's SaaS delivery path.
The next surface is the web interface: initially a governor operations dashboard, then the
customer-facing product, and ultimately the public face of CORE.

Two audiences are in scope, sequenced:

1. **Governor** — runtime dashboard, proposal queue, findings/blackboard, worker health.
   Replaces `core-admin runtime dashboard` and day-to-day CLI operations with a browser
   surface. Internal, single-user initially.
2. **Customers** — per-organisation GRC audit state, gap analysis, reports. Multi-tenant,
   public-facing, must withstand external scrutiny on design and security.

The architecture decided here is permanent infrastructure. CORE does not rebuild foundations.
This ADR must therefore over-invest in correctness and under-invest in speed-to-first-pixel.

---

## Decisions

### D1 — Architecture paradigm: SPA served by FastAPI

The web interface is a **Single-Page Application** (SPA). No Node.js server.

CORE already runs FastAPI as its API backend. Adding a second server runtime (Node.js for
Next.js or Remix) would mean:
- Two processes to run, monitor, and deploy in production.
- Two languages of server-side code to maintain.
- Duplicate session/auth logic (FastAPI holds the JWT and cookie; Next.js server actions
  would need to re-implement or forward).

The React team recommends full-stack frameworks (Next.js, React Router v7/Remix) as the
default for new projects — but that recommendation is for projects choosing their entire
stack. CORE already has a backend. The React team explicitly endorses **Vite** for projects
with an existing backend or "custom constraints." That is CORE's situation.

SSR's primary benefits (SEO, first-contentful-paint for public pages) do not apply here.
Every meaningful route is behind authentication. A cold-loaded SPA over a fast API is
indistinguishable from SSR for authenticated users.

Production serving: FastAPI mounts `web/dist/` and returns `index.html` for all non-API
paths (SPA catch-all). One process, one deployment artifact, one CORS origin.

### D2 — Framework and build tool: React 19 + TypeScript 5 + Vite 6

- **React 19** — current stable release. Mature ecosystem; largest hiring pool when CORE
  adds frontend engineers. The TanStack ecosystem (§D5, §D6, §D7) is React-first and
  deeply integrated. React 19's `use()` hook and improved Suspense are compatible with
  TanStack Query's data-fetching model.
- **TypeScript 5** — strict mode enabled from day one (`strict: true`). The contract
  between FastAPI and the frontend is enforced at build time via Orval (§D8), not at
  runtime. A type error in a generated hook is a broken API contract, caught in CI.
- **Vite 6** — build tool for SPA with non-JS backend. Sub-second HMR in development.
  `moduleResolution: "bundler"` eliminates import-extension noise. Dev server proxies
  `/v1` and `/auth` to FastAPI on `:8000`; production needs no proxy (same origin).
  Node.js 20.19+ required.

Scaffolding baseline: `npm create vite@latest web -- --template react-ts`

### D3 — Component system: shadcn/ui + Tailwind CSS v4

- **Tailwind CSS v4** — CSS-first configuration (`@import "tailwindcss"`, no
  `tailwind.config.js`). Utility-first; no style encapsulation battles; design tokens
  are CSS custom properties owned by CORE, not a library.
- **shadcn/ui** — not a component package; it is a component registry. Running
  `npx shadcn@latest add button` copies the component source into `web/src/components/ui/`.
  CORE owns and can edit every component. No version lock-in, no wrapper gymnastics, no
  fighting a library's opinionated styles when the public design language is defined. The
  open-code model also means Claude can read, understand, and generate new components that
  match existing patterns without hallucinating unknown APIs.

shadcn/ui uses **Radix UI** primitives underneath — fully accessible (ARIA, keyboard
navigation) at the primitive layer. CORE inherits accessibility without implementing it.

Design system progression:
- **Phase 1 (governor):** shadcn/ui defaults — functional, clean, no custom branding
  required. Governor knows what the interface is for.
- **Phase 2 (customers):** CORE's visual identity is applied via Tailwind CSS custom
  properties. Component code is already owned; no migration needed, only restyling.

### D4 — Data tables: TanStack Table v8 (via shadcn/ui)

The shadcn/ui data table guide uses TanStack Table as the headless data layer. This is the
correct split: TanStack Table handles sorting, filtering, pagination, and row selection as
pure logic; shadcn/ui primitives (`<Table>`, `<Button>`, `<DropdownMenu>`) render it.

Relevant surfaces: findings table, proposals queue, worker health, audit events log,
org membership management. All follow the same pattern; the composition is consistent.

### D5 — Server state: TanStack Query v5

TanStack Query is the async state management layer. It handles:
- **Caching** — API responses are cached and served stale-while-revalidating.
- **Background refetch** — the dashboard auto-updates without manual polling code.
- **Polling** — `refetchInterval` for live worker health and open findings count.
- **Mutations** — proposal approval/rejection with optimistic UI and automatic
  cache invalidation.
- **Query invalidation** — approving a proposal invalidates the proposals list and
  the findings count atomically.

TanStack Query replaces `useEffect` + `fetch` + local loading/error state — a pattern
that consistently produces bugs under concurrent renders. The governor dashboard needs
live data; TanStack Query's background-fetch model is built for exactly that.

### D6 — Routing: TanStack Router v1

TanStack Router provides **end-to-end type safety** for routes, path parameters, and
search parameters. Route definitions generate TypeScript types; navigating to a route with
the wrong parameters is a compile error, not a runtime 404.

This matters for a product that will grow: as routes are added (per-org audit pages,
per-proposal detail views, per-finding drill-down), type-safe navigation prevents
link-rot from refactors.

Key features used:
- **File-based routing** — route files in `web/src/routes/` map to URL segments.
  The file tree is the route tree. No separate route registration.
- **Loaders** — pre-fetch data for a route before it renders. Integrates with
  TanStack Query's `ensureQueryData` for cache-first loads.
- **Search parameter schemas** — query params (filters, pagination) are typed and
  validated. No `URLSearchParams` string parsing scattered through components.
- **Nested layouts** — the auth shell (sidebar, header, user menu) wraps all
  authenticated routes as a layout; the login/register screens get a bare layout.

### D7 — Route map

```
/                    → redirect to /dashboard (authenticated) or /login
/login               → LoginPage (unauthenticated layout)
/register            → RegisterPage (unauthenticated layout)

── authenticated layout (sidebar + header) ──────────────────────────────────
/dashboard           → RuntimeDashboard (worker health, convergence, inbox)
/proposals           → ProposalQueue (list, filter by status)
/proposals/$id       → ProposalDetail (approve / reject / inspect)
/findings            → FindingsList (blackboard findings, filter by rule/status)
/workers             → WorkerHealth (active workers, heartbeat, cycle counts)
/settings            → UserSettings (password, API keys)

── Phase 2 (customers) ──────────────────────────────────────────────────────
/org                 → OrgManagement (members, roles, invitations)
/audit               → AuditProjects (customer GRC surface)
/reports             → Reports (gap analysis, audit findings export)
```

Phase 1 implements: `/dashboard`, `/proposals`, `/proposals/$id`, `/findings`,
`/workers`, `/settings`, `/login`, `/register`.

### D8 — API contract: Orval v8 (OpenAPI → typed React Query hooks)

FastAPI generates an OpenAPI 3.x schema at `/openapi.json` automatically from route
definitions and Pydantic models. Orval v8 consumes this schema and generates:

- **TypeScript types** for every request/response model.
- **TanStack Query hooks** (`useQuery` / `useMutation`) for every API endpoint.

**What is committed vs. generated:**

| Artifact | Status | Reason |
|---|---|---|
| `web/openapi.json` | **committed** | API contract snapshot — the source of truth |
| `web/src/api/` | **gitignored** | Generated artifact — always rebuilt from the snapshot |

Committing the generated output (`web/src/api/`) would be the wrong model: generated
code drifts silently from its input and review noise is high. Committing the schema
snapshot (`web/openapi.json`) is the right model — it is the contract, it is human-
readable, it diffs cleanly in PRs, and Orval regenerates the hooks from it at build time
without requiring a running FastAPI server.

This is the same pattern as `poetry.lock`, `package-lock.json`, and `go.sum`: commit the
lockfile (contract), never commit the compiled artifacts.

**Orval configuration** lives in `web/orval.config.ts` pointing at the local snapshot:

```typescript
export default defineConfig({
  api: {
    input: './openapi.json',
    output: {
      mode: 'tags-split',
      target: './src/api',
      client: 'react-query',
      override: { mutator: { path: './src/lib/fetch-client.ts', name: 'customFetch' } },
    },
  },
})
```

**Schema update workflow** — two commands, both in `make web-generate-schema`:

1. Start FastAPI, fetch `http://localhost:8000/openapi.json`, write to `web/openapi.json`.
2. Run `npx orval` — regenerates `web/src/api/` from the updated snapshot.

The developer commits the updated `web/openapi.json`. The generated `web/src/api/` is
rebuilt by every subsequent `npm run build`.

**CI drift detection** — a dedicated CI step runs on every push:

```bash
# Start FastAPI
poetry run uvicorn src.api.main:app --port 8000 &
sleep 3
# Normalise both sides (jq -S = sorted keys, canonical whitespace) to eliminate
# key-order and whitespace churn that varies across FastAPI/pydantic versions.
curl -sf http://localhost:8000/openapi.json | jq -S . > /tmp/live-openapi.json
jq -S . web/openapi.json > /tmp/committed-openapi.json
diff /tmp/committed-openapi.json /tmp/live-openapi.json \
  || (echo "API schema drift — run: make web-generate-schema" && exit 1)
```

Raw `diff` on the un-normalised JSON is not used: FastAPI's serialization is not
byte-stable across versions (dict key ordering, indentation), so a raw comparison
would throw false drift failures on every minor FastAPI or pydantic upgrade with no
actual contract change. The `jq -S` normalisation is mandatory.

A Pydantic model change that is not accompanied by an updated `web/openapi.json` fails
CI immediately and loudly. There is no silent drift path.

TypeScript strict mode provides a second layer: even if someone bypasses the snapshot
update, any call site in component code that uses a deleted or reshaped hook will fail
to compile during `npm run build`.

### D9 — Repo structure

The frontend lives at `web/` in the CORE repository:

```
web/
  src/
    api/             ← gitignored — Orval-generated, rebuilt from openapi.json at build time
    components/
      ui/            ← shadcn/ui primitives (owned source)
      dashboard/     ← governor dashboard components
      auth/          ← login, register, verification screens
      layout/        ← sidebar, header, nav
    hooks/           ← custom React hooks
    routes/          ← TanStack Router file-based route tree
    lib/
      fetch-client.ts  ← custom fetch wrapper (401 interceptor — see D12)
      query-client.ts  ← TanStack QueryClient configuration
      utils.ts         ← cn() and other utilities
    types/           ← supplementary TypeScript types
  public/            ← static assets (favicon, og-image)
  index.html         ← Vite entry point
  openapi.json       ← committed API contract snapshot (source for Orval)
  orval.config.ts    ← Orval configuration (points at openapi.json)
  vite.config.ts
  tsconfig.json
  tsconfig.app.json
  package.json
  package-lock.json  ← committed (reproducible installs via npm ci)
  components.json    ← shadcn/ui registry config
  .gitignore         ← ignores node_modules/, dist/, src/api/, .env
  .env               ← VITE_ vars for local dev (gitignored)
  .env.production    ← production env overrides (VITE_API_BASE_URL empty = same origin)
```

The `web/` directory is not a Python package and is outside all Python constitutional
rule scopes.

Makefile targets added to root `Makefile`:
- `make web-install` — `npm ci` in `web/` (requires committed `package-lock.json`)
- `make web-dev` — Vite dev server on :5173, proxying to FastAPI on :8000
- `make web-build` — runs Orval then Vite build; outputs to `web/dist/`
- `make web-generate-schema` — fetches live FastAPI schema → updates `web/openapi.json`
  → regenerates `web/src/api/`; developer commits the updated `openapi.json`

### D10 — Development model

```
┌─────────────────────────┐      proxy /v1/*, /auth/*
│  Vite dev server :5173  │ ──────────────────────────► FastAPI :8000
│  HMR, instant reload    │                              (all API routes)
└─────────────────────────┘
         ▲
      browser
```

Two processes in development. The Vite dev server handles the frontend and proxies all
`/v1/*` and `/auth/*` requests to FastAPI. No CORS configuration needed in dev because
the proxy rewrites the origin.

`vite.config.ts` proxy block:

```typescript
server: {
  proxy: {
    '/v1':   { target: 'http://localhost:8000', changeOrigin: true },
    '/auth': { target: 'http://localhost:8000', changeOrigin: true },
  }
}
```

Environment variables follow Vite's `VITE_` prefix convention and are inlined at build
time. Variables without the prefix are server-side only and never exposed to the bundle.

### D11 — Production serving

FastAPI mounts the Vite build output and returns `index.html` for any path not matched
by an API route:

```python
# src/api/main.py — appended AFTER all API router registrations
from pathlib import Path
from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_WEB_DIST = Path(__file__).parents[2] / "web" / "dist"

if _WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_spa(full_path: str) -> FileResponse:
        # Exclude API prefixes so mistyped or unregistered /v1/* and /auth/* paths
        # return an honest 404 instead of index.html with a 200.  Without this, the
        # frontend receives HTML where it expected JSON and the error surfaces as a
        # JSON parse failure rather than a clean 404.
        if full_path.startswith(("v1/", "auth/")):
            raise HTTPException(status_code=404)
        return FileResponse(_WEB_DIST / "index.html")
```

The `if _WEB_DIST.exists()` guard allows core-api to start cleanly in API-only
environments (CI, headless deployments) before `web/dist/` is built.

**Two load-bearing invariants — known governance debt:**

1. **Ordering:** the SPA catch-all must be the last registered handler. Any `/v1/*` or
   `/auth/*` router registered after it is silently shadowed by `index.html`. Enforced
   by convention (a comment block at the mount site) until a constitutional rule can
   verify handler registration order.

2. **Prefix exclusion:** the `v1/` and `auth/` prefix guard in `_serve_spa` must be kept
   in sync with the actual API router prefixes. If a new router prefix is added without
   updating this guard, its 404s silently return HTML.

Both are convention-as-governance, which is the weakest enforcement posture in a system
whose thesis is "convention is not governance." A blocking constitutional rule is the
correct long-term fix; it is deferred to a follow-on ADR.

### D12 — Auth integration

Authentication uses the httpOnly cookie model established in ADR-124. The access JWT
cookie is sent automatically by the browser on every same-origin request. No
`Authorization` header management in the frontend; no token storage in `localStorage`
(XSS exposure).

Token refresh: TanStack Query has no built-in global retry-on-401 mechanism. The
refresh logic lives in `web/src/lib/fetch-client.ts` — a custom fetch wrapper that
every Orval-generated hook calls (configured via `orval.config.ts` `mutator`). On a
401 response, the wrapper calls `/auth/refresh` once and replays the original request.
If the refresh also returns 401, it clears local session state and redirects to
`/login`. All Orval-generated hooks inherit this behaviour automatically; no per-hook
error handling is needed.

**Single-flight refresh (required):** the governor dashboard loads multiple panels
concurrently and polls several endpoints. On a session expiry, concurrent requests
fire concurrent 401s simultaneously. A naïve "on 401 call refresh" implementation
fires N refresh requests; if ADR-124 rotates the refresh token on use, the second
request invalidates the first token and every subsequent replay gets a 401 → the
wrapper fires another refresh → logout loop on every cold load.

The wrapper must implement single-flight: all concurrent 401 responses await a single
shared refresh promise. New 401s that arrive while a refresh is in flight join the
same promise rather than spawning a new one. In `fetch-client.ts`:

```typescript
let refreshPromise: Promise<void> | null = null;

async function refreshOnce(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = fetch('/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(r => { if (!r.ok) throw new Error('refresh_failed'); })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}
```

Every concurrent 401 path calls `refreshOnce()` — only the first allocates the
promise; the rest await the same one.

**CSRF:** D12's httpOnly cookie model (auto-sent by the browser on every same-origin
request) is the classic CSRF-vulnerable shape. Mitigation requires the cookie to be
issued with `SameSite=Lax` or `SameSite=Strict`. The cookie attributes are set
server-side in the auth implementation governed by ADR-124; this ADR does not restate
them, but they are a pre-condition for Phase 2 ("must withstand external scrutiny on
security"). Verify ADR-124's cookie `Set-Cookie` attributes include `SameSite` before
any public-facing deployment. If ADR-124 does not specify `SameSite`, it must be
amended — not papered over here.

**CORS (T6b):** `allow_origins=["*"]` in `src/api/main.py` must be narrowed to
`["https://<production-domain>"]` before any public-facing deployment. This is a
one-line change once the domain is confirmed. It is a pre-condition for Phase 2, not
a post-launch task.

---

## Consequences

- Node.js 20.19+ enters the required developer toolchain and CI pipelines alongside
  Python 3.12. This is the most operationally significant consequence of this ADR.
- `web/node_modules/`, `web/dist/`, and `web/src/api/` are gitignored.
- `web/openapi.json` is committed as the API contract snapshot. `web/package-lock.json`
  is committed for reproducible installs. These are the only generated/lockfile artifacts
  that belong in git.
- `make web-generate-schema` must be run and the updated `web/openapi.json` committed
  in the same changeset as any FastAPI API surface change. CI enforces this via a schema
  drift check (D8); a missing update fails the build loudly rather than drifting silently.
- The FastAPI SPA catch-all (D11) carries two fragile invariants: (a) it must remain
  the last registered handler; (b) its API-prefix exclusion list (`v1/`, `auth/`) must
  stay in sync with actual router prefixes. Both are convention-enforced pending a
  constitutional rule. Any new API router prefix requires updating both the registration
  order and the exclusion guard simultaneously.
- `web/` is not governed by the Python audit engine. TypeScript strict mode, ESLint,
  and Prettier are the equivalent enforcement layer and must be configured and enforced
  in CI from the first commit of `web/`.
- Phase 1 adds `web/` with no changes to existing Python surfaces beyond the SPA mount
  in `src/api/main.py` and Makefile targets.
- T6b CORS tightening is a hard pre-condition for any public deployment.
- ADR-124's cookie `SameSite` attribute is a hard pre-condition for Phase 2; verify
  it is set to `Lax` or `Strict` before any public-facing deployment.
- `fetch-client.ts` must implement the single-flight refresh pattern (D12); a naïve
  per-request refresh loop produces a logout storm on concurrent 401s when ADR-124
  rotates refresh tokens on use.
- Google OAuth (T6e) and MFA (T6f) are deferred; the auth abstraction must not
  preclude either.

---

## References

- ADR-124 — User Access Control (auth contract this frontend consumes)
- T6a–T6f — SaaS delivery surfaces (`CORE-BYOR-Program-Backlog.md`)
- Vite backend integration — https://vite.dev/guide/backend-integration
- shadcn/ui — https://ui.shadcn.com
- TanStack Query — https://tanstack.com/query
- TanStack Router — https://tanstack.com/router
- TanStack Table — https://tanstack.com/table
- Orval — https://orval.dev
