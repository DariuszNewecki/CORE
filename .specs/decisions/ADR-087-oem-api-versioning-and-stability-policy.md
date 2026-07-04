---
kind: adr
id: ADR-087
title: ADR-087 — OEM API versioning and stability policy
status: accepted
---

<!-- path: .specs/decisions/ADR-087-oem-api-versioning-and-stability-policy.md -->

# ADR-087 — OEM API versioning and stability policy

**Date:** 2026-06-02
**Governing paper:** `.specs/papers/CORE-OEM-API.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-02 — drafted under Path A execute-verb authorization, F-40 decomposition path: "proceed as suggested" + governor pick of option 1 from the F-40.1 closure handoff)
**Grounding papers:** `papers/CORE-OEM-API.md` (F-40.1 public-vs-internal classification — establishes which routes this policy governs); `papers/CORE-Features.md#F-40` (the OEM API surface feature anchor); `papers/CORE-Product-Tiers.md` §3.5 (Embedded tier — third-party OEM integration is the consumer model this ADR enables).
**Related:** ADR-084 D6 (interface symmetry — every interface commercial code uses must be a documented public interface); ADR-085 §Context 5+3 row for F-40 ("documented public contract" as a precondition to ship); ADR-086 (Installation Architecture — the wire-version semantics established here coordinate with `core-runtime`'s PyPI semver); F-40 #414 (parent feature); F-40.1 #550 (classification — closed); F-40.3 #552 (OpenAPI spec — consumes this policy); F-40.4 #553 (sidecar verification — closes F-40 once this policy is honored by the spec).

---

## Context

### Why this ADR exists

F-40's exit criterion per ADR-085's 5+3 row requires a **documented public contract**. F-40.1 (#550) declared *which* routes are public; that classification is operationally clean. But "documented public contract" without **stability semantics** is empty — a third-party OEM partner cannot integrate against a surface whose shape can change silently between releases. They need to know: what kinds of changes are guaranteed safe? what kinds will break their integration? when does an integration need to be rewritten?

This ADR is the answer to those three questions for the F-40 public API surface (the 46 routes under `/v1/` and `/health` classified `public` in `papers/CORE-OEM-API.md` §3).

It does NOT govern:

- The CLI surface (`core-admin …`) — that's a different consumer model.
- The `.intent/` constitutional surface — governed by its own validation pipeline.
- The Python import surface of `core-runtime` — that's F-48.4's scope (public-vs-internal `__all__` declarations) and follows Python's own versioning convention.
- The Docker image tags — coordinated with PyPI semver per ADR-086 but not the wire-version of this ADR.

### Why now

F-40.2 sits between F-40.1 (which declared the route set) and F-40.3 (which annotates the routes as an OpenAPI spec). Without stability semantics declared first, F-40.3's OpenAPI spec would have nothing to say in its `info.version` or `x-stability` fields — the contract would describe shape without describing the shape's reliability.

This ADR is also a precondition for the deferred Phase-B work (F-40.5 auth, F-40.6 host binding). Both rely on the spec being a stable target: rate-limiting per-key per-route requires per-route to be a stable identifier; auth scopes typed against the OpenAPI shape requires the shape to be promised. The earlier this policy lands, the lower the cost of getting it wrong.

### Status quo

Today's `src/api/` already uses a `/v1/` URL prefix on all routes (mounted via `app.include_router(..., prefix="/v1", ...)` in `src/api/main.py`). The prefix exists; the semantics attached to it do not. Routes have been added, removed, and reshaped freely throughout CORE's development. This ADR draws the line: from acceptance forward, the `/v1/` surface has the semantics declared in D1–D7.

The current shape is **grandfathered** as the v1 baseline. D7 below makes the audit boundary explicit. Routes shipped before this ADR but classified `public` in `papers/CORE-OEM-API.md` are part of v1 as their current shape, frozen for compatibility purposes from this ADR's acceptance date.

---

## Decisions

### D1 — Wire version semantics: `/v1/` is the major-version boundary

The `/v1/` URL prefix is the **wire-protocol major-version identifier** for the OEM API surface. Semver minor and patch levels are implicit (they advance with every `core-runtime` release and are not surfaced on the wire); major levels are explicit and surface as a new URL prefix when bumped.

Specifically:

- **Major bump** (`/v1/` → `/v2/`): triggered by a breaking change to any route classified `public`. New routes are mounted under the new prefix; the old prefix continues to be served for the deprecation window declared in D5. Required when D2's rules do not permit the change in-place.
- **Minor bump** (e.g., `core-runtime 2.6.X → 2.7.0`): triggered by additive changes — new public routes, new optional fields on responses, new optional query parameters. Surfaces in the OpenAPI spec's `info.version` (which mirrors `core-runtime`'s PyPI version) but does NOT change the URL prefix.
- **Patch bump** (e.g., `2.7.0 → 2.7.1`): bug fixes, internal-only changes, documentation. No wire-visible change to public routes.

The URL prefix is the source of truth on the wire. The OpenAPI spec's `info.version` is the source of truth in the spec. They are bound: `/v1/openapi.json` must report a version whose major component equals 1.

### D2 — What constitutes a breaking change

A change to a route classified `public` is **breaking** if, after the change, a previously-compliant client request or response shape would fail validation or change observable behavior in a way the client can detect. Specifically:

- **Removing a route** — breaking.
- **Removing a method on a route** (e.g., `POST` → `DELETE` only) — breaking.
- **Removing a response field** — breaking.
- **Changing the type of a response field** — breaking (`str` → `int`, `Optional[str]` → `str` if the field could previously be null, etc.).
- **Changing the type of a request field's accepted shape** to a narrower set — breaking (relaxing is non-breaking).
- **Adding a required request field without a default** — breaking (existing clients would now send incomplete requests).
- **Changing observable side-effect semantics** of a write endpoint (e.g., a POST that previously created one row now creates two) — breaking.
- **Changing the HTTP status code** for a previously-successful response shape — breaking.
- **Tightening authentication or authorization** in a way that rejects previously-accepted credentials — breaking. (Adding auth where there was none initially — see D8 transition — is breaking in principle; the D8 transition section treats this as a one-time event predating v1's first stable release.)

A change is **non-breaking** if it is either fully additive or invisible to a compliant client:

- **Adding a new route** — non-breaking.
- **Adding a new method to an existing route** — non-breaking.
- **Adding an optional response field** — non-breaking (clients ignoring unknown fields keep working; clients consuming the new field opt in).
- **Adding an optional request field with a default** — non-breaking.
- **Adding a new value to a response enum** — non-breaking ONLY IF the field is documented as open-vocabulary; closed-vocabulary enum additions are breaking. Default closed unless explicitly annotated open in the OpenAPI spec.
- **Loosening request validation** (accepting strings that were previously rejected) — non-breaking.
- **Internal implementation changes** that don't affect the wire — non-breaking.

When a change's classification is ambiguous, **default to "breaking"**. The author of the change must affirmatively justify why a borderline change is safe.

### D3 — Field-addition + field-removal rules

Additive changes (new optional fields, new routes, new methods, new optional request parameters) **may** land in any release. The OpenAPI spec is regenerated; consumers reading from the spec discover the addition. No coordination required.

Removal of a public field, route, or method is **forbidden** within a major version. Removal requires:

1. Marking the artifact deprecated (D4) in release N.
2. Maintaining its functional behavior through the deprecation window (D5).
3. Removing it ONLY at the major bump (`/v2/` mount), with the prior version remaining served at `/v1/` through the deprecation window from D5.

A renamed field is a removal-plus-addition for purposes of this policy. Rename a public field only at major bumps. Internal-only renames (a Pydantic model's field renamed to a Python identifier that doesn't appear on the wire because of a `Field(alias=...)`) are not in scope here.

### D4 — Deprecation lane

A public route, method, field, or query parameter can be **marked deprecated** at any release. Deprecation is a signal to consumers, not yet a removal. The mechanism:

1. **In the OpenAPI spec**: the artifact carries `deprecated: true` on its OpenAPI object (route, parameter, schema property — wherever the spec supports it).
2. **In the response (for deprecated routes only)**: the response includes a `Deprecation: true` header AND a `Sunset: <RFC 3339 date>` header indicating when the route's behavior will be removed. RFC 8594 + RFC 9745.
3. **In the docs**: `papers/CORE-OEM-API.md` §"Deprecation candidates" enumerates current deprecated artifacts with their introduction-of-deprecation date and planned sunset date.

Deprecation is **purely informational** during the deprecation window. The route/field continues to function identically; only its long-term future is signaled.

### D5 — Deprecation window: minimum six months

The minimum window between marking an artifact deprecated and removing it is **six months**, measured from the first release in which the deprecation marker appears to the first release in which the artifact is removed. Six months is the floor; longer windows (12 months for routes with high consumer surface, indefinite for routes a sidecar relies on) are permitted.

Six months balances:

- **Operational reality** — OEM integrators are typically third-party teams with their own roadmaps; less than six months produces uncomfortable forced-migration windows.
- **Engineering velocity** — longer-than-six-month windows risk accumulating deprecated debt that's never cleaned up.
- **Industry convention** — Stripe, Twilio, AWS, and similar OEM-grade APIs all use windows in the 6–12 month range.

Removal of a deprecated artifact requires the bump from `/v1/` to `/v2/` per D3 — there is no in-place removal. This means deprecation is in practice a *signal for the next major version*; if no `/v2/` is yet planned, the deprecation marker can persist beyond six months (the artifact stays functional, the warning stays visible).

### D6 — `/v2/` migration policy

A `/v2/` URL prefix is mounted alongside `/v1/` when one of the following triggers:

1. **Accumulated breaking changes** — three or more independent breaking changes have been deferred to a `/v2/`-marker queue and are ready to land together.
2. **Fundamental redesign** — a single change that's so large (e.g., re-architecting the proposal queue surface) that landing it under `/v1/` would require violating D2's "additive-only" rule even with extensive deprecation effort.
3. **Stability of the new shape requires it** — a redesigned route family needs the freedom to evolve under fresh semver promises without inheriting `/v1/` consumers' expectations.

When `/v2/` is cut:

- The old `/v1/` prefix continues to serve **only the routes that were not redesigned for v2**, plus those routes that were redesigned but still need backwards-compatible operation through the deprecation window from D5.
- The OpenAPI spec splits: `/v1/openapi.json` describes the v1 surface (still served, possibly with deprecated markers everywhere); `/v2/openapi.json` describes the new surface.
- `core-runtime`'s PyPI release notes name the cut: "v1 → v2 transition begins in core-runtime X.Y.Z; v1 sunset planned for core-runtime A.B.C (target date)."
- Sidecars depending on the changed routes have ≥6 months to migrate per D5.

No `/v2/` is currently planned. This ADR enables one to be cut cleanly when needed; it does not schedule one.

### D7 — Grandfathered baseline

The current shape of every route classified `public` in `papers/CORE-OEM-API.md` §3 (commit `22144571`, 2026-06-02) is the **v1 baseline**. From this ADR's acceptance forward:

- Changes to those routes are subject to D2 / D3.
- The OpenAPI spec emitted by F-40.3 (issue #552) describes them at this baseline shape.
- A route that was added under `/v1/` BEFORE this ADR but that turns out to have a defect in its baseline shape (poor naming, awkward response structure, missing field) can be either: (a) deprecated and replaced by a sibling route with the better shape, per D4 + D5; (b) accepted as v1 debt and corrected in `/v2/`.

There is no "freeze period" during which the baseline can be revised in place. Either the route lands now and is governed by this ADR from acceptance, or it's not part of v1 and gets reclassified `internal` in `papers/CORE-OEM-API.md`.

### D8 — Authentication transition (notably out of scope for this ADR)

Today the OEM API surface is served on `127.0.0.1:8000` with no authentication. F-40.5 (#554) adds authentication. The **introduction** of authentication is a one-time event preceding v1's first commercially-deployed release; consumers existing today do so on the assumption that the daemon they hit is theirs.

When auth lands per F-40.5:

- It is **breaking by D2's definition** (requests without credentials that were previously accepted would be rejected).
- It is **explicitly carved out from D6's `/v2/` requirement** under the rationale that no third-party OEM consumer exists yet (F-40 hasn't shipped at the time of writing); pre-shipping changes don't trigger the major bump.
- The F-40.5 work itself must define a transition rule: probably an env var or config flag enabling auth, defaulting off in development and on in production deployments.
- After F-40.5 ships, the carve-out closes: subsequent auth-related changes (algorithm upgrades, scope additions) are governed by D2 normally.

### D9 — OpenAPI spec is the publication mechanism for this policy

Every claim made by this ADR is realized through the OpenAPI spec produced by F-40.3 (#552). The spec carries:

- `info.version` mirroring `core-runtime`'s PyPI version (e.g., `2.6.0`).
- `info.x-stability-policy: https://github.com/DariuszNewecki/CORE/blob/main/.specs/decisions/ADR-087-oem-api-versioning-and-stability-policy.md` — a link consumers can follow.
- Per-route `deprecated: true` markers where applicable.
- Per-schema closed-vs-open-vocabulary annotations on enums (e.g., `x-vocabulary: closed`).

A consumer reading the spec without reading this ADR should still be able to follow the marker conventions. This ADR documents the *why*; the spec is the *what*.

---

## Consequences

### Enables

- **F-40.3 (#552)** can author the OpenAPI spec with concrete decisions about `info.version`, deprecation markers, and the closed-enum convention.
- **F-40.4 (#553)** can verify each sidecar attaches against routes whose stability semantics are now declared.
- **F-40.5 (#554)** has a documented carve-out (D8) for the auth-introduction event.
- **First commercial sidecar work** (F-20, F-34, F-45) can begin design against a target whose evolution rules are known.
- **Third-party OEM partnerships**, when they materialize, have a reference document to point at when asking "what's your stability promise."

### Forbids

- **Silent removal of public routes/fields/methods** within a major version. Anything removed must pass through D4's deprecation lane and D5's six-month window.
- **In-place breaking changes** to v1 routes. The path is always: deprecate → wait → cut `/v2/` → eventually retire `/v1/`.
- **Per-route stability promises divergent from this ADR.** Routes don't get to opt out; all `public` routes are governed identically.

### Costs

- **Deprecation lane requires discipline.** Adding a deprecated marker is cheap; removing the marker (because the deprecation was reversed) is also fine. But forgetting that an artifact is deprecated, then accidentally evolving it (adding fields, changing behavior in a way that's intended for production but unintended for the sunset path), is an error mode this ADR cannot prevent.
- **`/v2/` cut is operationally heavy.** Serving two URL prefixes concurrently for ≥6 months requires the engine to support both shapes. This is intentional cost — it forces the major bump to be a deliberate decision, not an accident.
- **Six-month windows constrain velocity.** When a redesign is desirable, the cost of doing it through this policy (deprecate now, wait 6 months, cut `/v2/`) competes with the alternative (accept the v1 shape as debt for one more cycle). The policy will sometimes lose that competition; that's by design.

### Downstream effects

- **F-48.5 (#541 — semver policy doc)** should reference this ADR for the wire-version semantics of `/v1/`. F-48.5 governs the Python-import-surface semver of `core-runtime` (different layer); the two policies should not contradict each other on the meaning of "breaking change" for shared concepts.
- **ADR-086 (Installation Architecture)** coordinates with this ADR on the mapping between `core-runtime` PyPI versions and `/v1/` wire semantics. Per D1: PyPI major version and `/v1/` major version are independent — `core-runtime` may bump major (1.0.0) while staying on `/v1/`, and vice versa, but the OpenAPI spec's `info.version` mirrors PyPI.
- **`papers/CORE-OEM-API.md`** gets a §"Versioning & stability — see ADR-087" reference added in F-40.3's edit pass.

---

## References

- **Parent feature:** F-40 #414 OEM API surface
- **Predecessor sub-issue:** F-40.1 #550 (route classification — closed)
- **This ADR's sub-issue:** F-40.2 #551 (closes on this ADR's commit)
- **Successor sub-issues:** F-40.3 #552 (OpenAPI spec), F-40.4 #553 (sidecar verification — closes F-40)
- **Constitutional anchors:** ADR-084 D6 (interface symmetry), ADR-085 §Context 5+3 row (F-40 exit criterion)
- **Coordination:** ADR-086 (Installation Architecture), F-48.5 #541 (Python-surface semver policy — different layer)
- **External conventions referenced:** RFC 8594 (`Sunset` HTTP header), RFC 9745 (`Deprecation` HTTP header)
