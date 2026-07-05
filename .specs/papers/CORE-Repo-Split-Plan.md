# CORE Repo Split Plan
*Public OSS runtime / private commercial platform separation*
*Agreed: 5 July 2026*

---

## Context

CORE is being restructured from a single repository into a public OSS runtime and a private commercial platform. This plan records all decisions made and the phased execution sequence. No implementation should begin without referencing this document.

---

## Locked decisions

| Decision | Answer |
|---|---|
| OSS auth model | No auth — local API, trusted localhost, no tokens or user accounts |
| Repo split strategy | Clean cut forward from an agreed commit boundary; no git history surgery |
| Timing | Split before the pharma pilot demo (PROJ-26.001) |
| DB schema | Separate — commercial tables (users, orgs, invitations, API keys) move to a `core-platform` schema migration; the public runtime schema contains only what the OSS runtime actually uses |
| GRC catalog boundary | Public catalogs: NIST 800-171, GDPR, CFR Part 11, EU Annex 11, NIS2, CyFun (all publicly-accessible regulation). Private catalogs: ISO 27001, GAMP 5 (licensed/paid standards). |
| Commercial repo name | `core-platform` (not `core-console` — the repo will contain more than just the Console UI) |

---

## OSS boundary principle

If a regulatory standard or guideline is publicly accessible, its CORE catalog is publicly accessible too. The commercial moat is not hiding public information — it is the licensed catalog content, internal corpus augmentation, evidence export quality, and maintained catalog updates.

CORE must be philosophically complete as a standalone product. A developer in a regulated industry can run a real GRC gap analysis from the CLI for free. Nothing essential is withheld.

---

## Target repo structure

```
DariuszNewecki/CORE              public, MIT-licensed
  core-runtime Python package
  CLI (core-admin, core)
  local daemon
  Mind / Body / Will engine
  public API contract
  public GRC catalogs (NIST, GDPR, CFR Part 11, EU Annex 11, NIS2, CyFun)
  starter intent / BYOR mechanics
  docs and examples

private/core-platform            commercial product monorepo
  apps/console/                  React/Vite web UI (moved from web/)
  services/uac/                  auth, orgs, invitations, API keys, email
  api/                           commercial routes mounted on runtime API
  grc/                           licensed catalog integration
  connectors/                    enterprise integrations (roadmap)
  infra/                         hosted deployment, billing, licensing

private/core-grc-catalogs        licensed catalog content
  iso_27001/
  gamp5/
```

---

## What moves where

### Moves to `core-platform`

| Item | Current location | Reason |
|---|---|---|
| React web app | `web/` | Console UI is a commercial surface |
| SPA mount in API | `src/api/main.py` (~10 lines) | Couples OSS runtime to Console delivery |
| Auth routes | `src/api/v1/auth_routes.py` | Multi-tenant product infrastructure, not runtime governance |
| Auth service | `src/body/services/auth/` | Creates orgs, memberships, tokens, invitations |
| Auth runner | `src/will/governance/auth_runner.py` | Will facade for auth service |
| DB tables | users, orgs, invitations, api_keys, memberships | Commercial data model |

### Moves to `core-grc-catalogs`

| Catalog | Reason |
|---|---|
| ISO 27001 | Licensed ISO standard; ISO sells it |
| GAMP 5 | Licensed ISPE guideline; ISPE sells it |

### Stays in `CORE` (public)

| Item | Reason |
|---|---|
| Mind / Body / Will engine | Trust engine and adoption wedge |
| CLI and local daemon | Core developer surface |
| Public API contract (FastAPI routes) | Useful for integrations; commercial routes are additive |
| GRC engine code | Resolver, gap analysis service, schema, verdict models — mechanism is the OSS proof |
| Public regulation catalogs | NIST 800-171, GDPR, CFR Part 11, EU Annex 11, NIS2, CyFun |
| `.intent/` and governance papers | Credibility layer, not the moat |
| ADR-116 (sanitized) | Architecture stays public; commercial moat wording moves to private specs |

---

## Execution phases

### Phase 0 — Guard rails
*Before any file moves. Zero risk.*

Add hard `.gitignore` exclusions and a CI gate that fails if protected paths are staged. This establishes the clean-cut boundary. Nothing should be committed to the public repo after this point that belongs in the commercial stack.

Protected paths to exclude from public repo:
```gitignore
grc-catalogs/licensed/
grc-catalogs/internal/
web/dist/
web/node_modules/
core-platform/
*.entitlement.yaml
```

Also verify `grc-catalogs/internal/` is covered by ADR-116 guardrails.

---

### Phase 1 — Extract `web/` and remove SPA mount
*Effort: ~1 day. Risk: none.*

- Move `web/` directory to `core-platform/apps/console/`
- Remove the conditional SPA mount (~10 lines) from `src/api/main.py`
- The public API remains; it simply no longer serves a UI

The SPA mount is already conditional on `web/dist/` existing, so this is a clean removal.

---

### Phase 2 — Extract UAC
*Effort: 2–3 days. One design dependency (DB schema — see below).*

Files to move to `core-platform/services/uac/`:
- `src/body/services/auth/` (service, tokens, deny_list, email, password)
- `src/api/v1/auth_routes.py`
- `src/will/governance/auth_runner.py`

Changes to the runtime:
- Remove auth router registration from `src/api/main.py`
- Remove `deny_list` import from `src/body/infrastructure/lifespan.py` — in OSS no-auth mode the revocation list is meaningless; remove or replace with a no-op stub
- Simplify `src/api/dependencies.py` — remove `decode_access_token` and `deny_list` imports; replace role guards with open local-mode stubs

**DB schema decision (agreed):** commercial tables (users, orgs, invitations, api_keys, memberships) are removed from the public runtime schema (`infra/sql/db_schema_live.sql`) and move to a `core-platform` schema migration that extends the runtime schema. The public schema reflects only what the OSS runtime actually uses.

---

### Phase 3 — GRC catalog split
*Effort: ~1 day, plus ADR-116 sanitization.*

- Move `grc-catalogs/iso_27001/` and `grc-catalogs/gamp5/` to `private/core-grc-catalogs/`
- All other catalogs (NIST 800-171, GDPR, CFR Part 11, EU Annex 11, NIS2, CyFun) remain in the public repo
- Update `grc-catalogs/inventory.yaml` in the public repo — list only the public catalogs; remove ISO 27001 and GAMP 5 entries
- Sanitize ADR-116 — keep the architecture description public; move commercial moat wording and private repo naming details to `.specs/commercial/` private notes
- Add CI gate: fail if anything under `grc-catalogs/licensed/` or `grc-catalogs/internal/` is staged

---

### Phase 4 — `core-platform` bootstrap
*Effort: 2–3 days.*

Create the private `core-platform` repo and wire it to extend the runtime:

```python
# core-platform entry point
from core_runtime.api import create_runtime_app
from core_platform.api import mount_commercial_routes

app = create_runtime_app()
mount_commercial_routes(app)  # adds /auth, /console, /orgs, /api-keys
```

`core-platform/pyproject.toml` depends on `core-runtime` as an installable package. Commercial workers connect to the same PostgreSQL instance and post to the same blackboard — no changes needed to the daemon/worker pattern.

Wire the GRC gap analysis service to read licensed catalogs from `core-grc-catalogs` when available.

---

### Phase 5 — Pharma demo (PROJ-26.001)
*Unblocked after Phase 4.*

With `core-platform` running against `core-grc-catalogs` (ISO 27001, GAMP 5, EU Annex 11, CFR Part 11), build the synthetic SOP/WI corpus and run the full GRC gap analysis demo. This is the first thing that runs exclusively from the commercial stack and the first `core-platform` sale candidate.

---

## Sequence and effort summary

| Phase | Description | Effort | Risk |
|---|---|---|---|
| 0 | Guard rails | 1 day | None |
| 1 | Extract `web/` + SPA mount | 1 day | None |
| 2 | Extract UAC + OSS auth mode | 2–3 days | Low — auth coupling is shallow |
| 3 | GRC catalog split + ADR-116 sanitization | 1 day | None |
| 4 | `core-platform` bootstrap | 2–3 days | Low |
| 5 | Pharma demo | Separate workstream | Unblocked after Phase 4 |

Total to clean split: roughly **7–9 focused engineering days**.

---

## OSS auth model detail

The runtime API runs on localhost with no authentication. This is the correct model for a local developer tool — the same pattern used by the Docker daemon, Prometheus, and many other local infrastructure components.

- No users, no orgs, no tokens, no email flows
- `core-admin` talks to the local API without credentials
- Single operator assumption: whoever runs the daemon owns the runtime
- For CI integrations: a single static env-var token (`CORE_TOKEN`) is sufficient if basic protection is needed; this does not require the full UAC stack

The full multi-tenant UAC (orgs, invitations, RBAC, API keys) is a `core-platform` commercial feature used when multiple human identities need governed access to a shared Console instance.

---

## What `core-platform` adds on top of the runtime

`core-platform` is additive. It imports `core-runtime` and extends it. It never modifies the runtime in place.

| Layer | Mechanism |
|---|---|
| Commercial API routes | FastAPI router mounting on top of the runtime app |
| UAC / multi-tenancy | `core-platform/services/uac/` — full org/user/invitation/API key stack |
| Console UI | React app served by `core-platform`; talks to the combined API |
| Licensed GRC catalogs | `core-platform` reads from `core-grc-catalogs` at runtime |
| Commercial workers | Connect to same PostgreSQL/blackboard as runtime workers |
| Commercial DB tables | Applied via `core-platform` schema migration on top of the runtime schema |
