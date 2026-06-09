# src/api/main.py

"""
API Main Entry Point — composition root.

FastAPI requires `lifespan` to be declared at app creation, so this file
imports `core_lifespan` from Body to wire the startup/shutdown sequence.
Composition roots wire layers together by design and are not layer bypasses.

CONSTITUTIONAL STATUS:
- Exempted from `architecture.api.no_body_bypass` via the composition-root
  sanctuary in `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  (added 2026-04-19). Analogous to the bootstrap sanctuary granted under
  `architecture.shared.no_layer_imports` for shared-layer composition files.
- F-40.3 (#552): OpenAPI metadata (title, version, description, x-stability-
  policy) declared here per ADR-087 D9. Version is read dynamically from
  `core-runtime`'s installed package metadata; source-tree runs report
  `0.0.0+source` to make the dev-mode origin visible in the spec.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from fastapi import FastAPI

from api.errors import register_exception_handlers
from api.v1 import (
    audit_routes,
    census_routes,
    coverage_routes,
    daemon_routes,
    development_routes,
    fix_routes,
    inspect_routes,
    integration_routes,
    integrity_routes,
    knowledge_routes,
    lint_routes,
    proposals_routes,
    quality_routes,
    refactor_routes,
    sync_routes,
)
from body.infrastructure.lifespan import core_lifespan
from shared.logger import getLogger


logger = getLogger(__name__)


_ADR_087_URL = (
    "https://github.com/DariuszNewecki/CORE/blob/main/.specs/decisions/"
    "ADR-087-oem-api-versioning-and-stability-policy.md"
)
_OEM_API_PAPER_URL = (
    "https://github.com/DariuszNewecki/CORE/blob/main/.specs/papers/CORE-OEM-API.md"
)


def _resolve_runtime_version() -> str:
    """Read core-runtime's PyPI version; fall back to a dev marker in source-tree mode.

    Per ADR-087 D9, OpenAPI ``info.version`` mirrors ``core-runtime``'s PyPI
    version. When the API runs from a source tree (no wheel installed),
    importlib.metadata can't find the distribution; emit a PEP-440
    local-version marker so consumers reading the spec see source-mode
    origin instead of a stale hardcoded number.
    """
    try:
        return _pkg_version("core-runtime")
    except PackageNotFoundError:
        return "0.0.0+source"


_OEM_API_DESCRIPTION = (
    """
The CORE OEM API surface — the stable, versioned interface that commercial
sidecars (F-20 convergence dashboard, F-34 web dashboard, F-45 hosted
findings dashboard) and third-party OEM integrators consume to embed
CORE's constitutional governance layer.

**Stability policy:** see [ADR-087]("""
    + _ADR_087_URL
    + """).
**Route classification:** see [CORE-OEM-API paper]("""
    + _OEM_API_PAPER_URL
    + """).

Routes marked `internal` (or absent from this spec) are CORE-operator
concerns — daemon lifecycle, autonomy-loop triggers, CI gate dispatch.
They are subject to change without notice and not part of this contract.
"""
)


# ID: 2751f337-a513-4f6d-8f35-b9d7055faac0
def create_app() -> FastAPI:
    """Compose the FastAPI app for the daemon + OEM API surface.

    The app serves both the public OEM API (routes annotated public per
    F-40.1's classification) and CORE-internal routes (marked
    ``include_in_schema=False`` per router; reachable but absent from
    the published OpenAPI spec). The split lets `/v1/openapi.json` be
    the authoritative source of the F-40 contract while the daemon
    still exposes the operator surface a CORE deployment needs.
    """
    app = FastAPI(
        title="CORE OEM API",
        version=_resolve_runtime_version(),
        description=_OEM_API_DESCRIPTION,
        lifespan=core_lifespan,
        # ADR-087 D2 + D7: fastapi 0.132 introduced default-strict Content-Type
        # checking on JSON requests. That is a request-shape tightening per D2
        # ("narrower accepted shape — breaking"). The grandfathered v1 baseline
        # under D7 accepted requests without a Content-Type header. Opt out to
        # preserve that baseline; the strict default can be revisited at the
        # next /v2/ cut.
        strict_content_type=False,
        openapi_tags=[
            {
                "name": "Audit",
                "description": "Audit runs + remediation triggers (public).",
            },
            {
                "name": "Census",
                "description": "Convergence-metric snapshots + baselines (public).",
            },
            {
                "name": "Inspect",
                "description": "Read-only state introspection (public).",
            },
            {"name": "Proposals", "description": "Autonomous-proposal queue (public)."},
            {"name": "Fix", "description": "Atomic-action dispatch (public)."},
            {"name": "Actions", "description": "Atomic-action registry (public)."},
            {"name": "Knowledge", "description": "Knowledge-graph query (public)."},
            {
                "name": "Coverage",
                "description": "Coverage runs + reports (mixed public/internal).",
            },
            {
                "name": "Refactor",
                "description": "Refactor candidates + dispatch (mixed public/internal).",
            },
        ],
    )
    app.include_router(knowledge_routes.router, prefix="/v1", tags=["Knowledge"])
    app.include_router(development_routes.router, prefix="/v1", tags=["Development"])
    app.include_router(proposals_routes.router, prefix="/v1", tags=["Proposals"])
    app.include_router(audit_routes.router, prefix="/v1", tags=["Audit"])
    app.include_router(integration_routes.router, prefix="/v1", tags=["Integration"])
    app.include_router(lint_routes.router, prefix="/v1", tags=["Lint"])
    app.include_router(fix_routes.router, prefix="/v1", tags=["Fix"])
    app.include_router(fix_routes.actions_router, prefix="/v1", tags=["Actions"])
    app.include_router(quality_routes.router, prefix="/v1", tags=["quality"])
    app.include_router(coverage_routes.router, prefix="/v1", tags=["Coverage"])
    app.include_router(coverage_routes.tests_router, prefix="/v1", tags=["Coverage"])
    app.include_router(refactor_routes.router, prefix="/v1", tags=["Refactor"])
    app.include_router(inspect_routes.status_router, prefix="/v1", tags=["Inspect"])
    app.include_router(inspect_routes.decisions_router, prefix="/v1", tags=["Inspect"])
    app.include_router(inspect_routes.refusals_router, prefix="/v1", tags=["Inspect"])
    app.include_router(inspect_routes.analysis_router, prefix="/v1", tags=["Inspect"])
    app.include_router(inspect_routes.components_router, prefix="/v1", tags=["Inspect"])
    app.include_router(inspect_routes.search_router, prefix="/v1", tags=["Inspect"])
    app.include_router(census_routes.router, prefix="/v1", tags=["Census"])
    app.include_router(sync_routes.router, prefix="/v1", tags=["Sync"])
    app.include_router(integrity_routes.router, prefix="/v1", tags=["Integrity"])
    app.include_router(daemon_routes.router, prefix="/v1", tags=["Daemon"])
    register_exception_handlers(app)

    @app.get(
        "/health",
        tags=["Health"],
        summary="Liveness probe",
        description=(
            "Returns 200 OK whenever the API process is responsive. "
            "Public; unauthenticated; safe to poll at high frequency."
        ),
    )
    # ID: 7e958d32-1b47-43a5-836b-f6df51d6b803
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # ADR-087 D9: inject x-stability-policy into the published OpenAPI spec.
    # FastAPI's constructor doesn't accept arbitrary x-* extensions on the
    # `info` object, so override `app.openapi` to post-process the generated
    # schema once and cache it on first access (FastAPI's own pattern).
    _default_openapi = app.openapi

    # ID: 6f1d3a7e-8c2b-4a05-b9f4-2e6c1a5d8b07
    def _openapi_with_stability_policy() -> dict:
        schema = _default_openapi()
        schema.setdefault("info", {})["x-stability-policy"] = _ADR_087_URL
        return schema

    app.openapi = _openapi_with_stability_policy  # type: ignore[method-assign]

    return app


app = create_app()
