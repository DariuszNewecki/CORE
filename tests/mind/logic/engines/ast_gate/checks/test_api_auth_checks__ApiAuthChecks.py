"""Tests for ApiAuthChecks — router_exposure_enforcement and route_module_must_declare_exposure (ADR-132 D7)."""

from __future__ import annotations

import ast
import textwrap

from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks


def _parse(src: str) -> ast.AST:
    return ast.parse(textwrap.dedent(src))


# ── happy paths — single router ───────────────────────────────────────────────


def test_governor_only_with_dependency_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_without_router_dependency_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data")
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_with_secondary_router_gate_passes() -> None:
    """Secondary router with require_governor is fine in a user-facing file.

    Being more restrictive than the file tier is allowed. The checker only
    constrains the primary 'router' variable for user-facing files.
    """
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/mixed")
        admin_router = APIRouter(prefix="/mixed/admin", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_no_router_exposure_skips_file() -> None:
    """Files without ROUTER_EXPOSURE are not API route modules; skip silently."""
    tree = _parse("""
        router = APIRouter(prefix="/stuff", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_depends_wrapped_require_governor_passes() -> None:
    """Accepts both bare require_governor and Depends(require_governor) in dependencies."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[Depends(require_governor)])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_governor_only_multiple_routers_all_gated_passes() -> None:
    """Every APIRouter in a governor-only file carries the gate — no violation."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
        admin_router = APIRouter(prefix="/admin", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


def test_user_facing_multiple_routers_none_gated_passes() -> None:
    """Multiple ungated routers in a user-facing file — no violation."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/fix")
        actions_router = APIRouter()
    """)
    assert ApiAuthChecks.check_router_exposure_enforcement(tree) == []


# ── violations — single router ────────────────────────────────────────────────


def test_governor_only_missing_dependency_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]
    assert "require_governor" in violations[0]
    assert "'router'" in violations[0]


def test_governor_only_wrong_dependency_is_violation() -> None:
    """A different dependency in the list is not a substitute for require_governor."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[get_current_user])
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]


def test_user_facing_with_router_level_dependency_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data", dependencies=[require_governor])
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "user-facing" in violations[0]
    assert "require_governor" in violations[0]


def test_unknown_exposure_value_is_violation() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "internal"
        router = APIRouter(prefix="/x")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "unrecognised" in violations[0]
    assert "internal" in violations[0]


# ── violations — multiple routers (the previously blind case) ─────────────────


def test_governor_only_secondary_router_missing_gate_is_violation() -> None:
    """Secondary router without require_governor in a governor-only file is a violation.

    Previously the checker only inspected 'router' and would have missed
    'ops_router' entirely.
    """
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/admin", dependencies=[require_governor])
        ops_router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 1
    assert "governor-only" in violations[0]
    assert "'ops_router'" in violations[0]


def test_governor_only_both_routers_missing_gate_reports_both() -> None:
    """Every ungated router in a governor-only file produces its own finding."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/admin")
        ops_router = APIRouter(prefix="/ops")
    """)
    violations = ApiAuthChecks.check_router_exposure_enforcement(tree)
    assert len(violations) == 2
    names_in_findings = " ".join(violations)
    assert "'ops_router'" in names_in_findings
    assert "'router'" in names_in_findings


# ── route_module_must_declare_exposure ────────────────────────────────────────


def test_exposure_declared_passes() -> None:
    """Any file with ROUTER_EXPOSURE present passes the completeness check."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])
    """)
    assert ApiAuthChecks.check_route_module_must_declare_exposure(tree) == []


def test_user_facing_exposure_declared_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data")
    """)
    assert ApiAuthChecks.check_route_module_must_declare_exposure(tree) == []


def test_missing_exposure_is_violation() -> None:
    """A route module with no ROUTER_EXPOSURE declaration fires the rule."""
    tree = _parse("""
        router = APIRouter(prefix="/ungoverned")
    """)
    violations = ApiAuthChecks.check_route_module_must_declare_exposure(tree)
    assert len(violations) == 1
    assert "ROUTER_EXPOSURE" in violations[0]


def test_empty_module_is_violation() -> None:
    """An entirely empty route module has no ROUTER_EXPOSURE."""
    tree = _parse("")
    violations = ApiAuthChecks.check_route_module_must_declare_exposure(tree)
    assert len(violations) == 1


# ── sensitive_route_must_be_gated (#770) ───────────────────────────────────────


def test_governor_only_module_never_flagged() -> None:
    """governor-only modules are already fully gated at the router-constructor
    level — the per-route check doesn't even apply to them."""
    tree = _parse("""
        ROUTER_EXPOSURE = "governor-only"
        router = APIRouter(prefix="/ops", dependencies=[require_governor])

        @router.post("/danger")
        async def do_danger():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_get_route_never_flagged() -> None:
    """Read-only GET routes are never sensitive regardless of gating."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/data")

        @router.get("/items")
        async def list_items():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_ungated_post_route_on_user_facing_module_is_violation() -> None:
    """The core gap (#770): a mutation route with no gate anywhere ships silently."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/secrets")

        @router.post("")
        async def set_secret():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "set_secret" in violations[0]
    assert "'post'" in violations[0]


def test_all_four_mutation_verbs_detected() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/x")

        @router.post("/a")
        async def a():
            ...

        @router.put("/b")
        async def b():
            ...

        @router.delete("/c")
        async def c():
            ...

        @router.patch("/d")
        async def d():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 4


def test_decorator_dependencies_gate_passes() -> None:
    """Gated via dependencies=[require_governor] on the route decorator."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/proposals")

        @router.post("/create", dependencies=[require_governor])
        async def create_proposal():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_decorator_depends_wrapped_gate_passes() -> None:
    """Depends(require_governor) form in the decorator's dependencies also counts."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/proposals")

        @router.post("/create", dependencies=[Depends(require_governor)])
        async def create_proposal():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_parameter_default_gate_passes() -> None:
    """Gated via a handler parameter defaulting to require_governor (the
    FastAPI DI-parameter idiom used elsewhere in this codebase)."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/proposals")

        @router.post("/create")
        async def create_proposal(user: dict = require_governor):
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_parameter_default_depends_wrapped_gate_passes() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/proposals")

        @router.post("/create")
        async def create_proposal(user: dict = Depends(require_governor)):
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_mixed_gated_and_ungated_routes_only_flags_ungated() -> None:
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/mixed")

        @router.post("/gated", dependencies=[require_governor])
        async def gated_route():
            ...

        @router.post("/ungated")
        async def ungated_route():
            ...

        @router.get("/read")
        async def read_route():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "ungated_route" in violations[0]


# ── INTENTIONALLY_UNGATED marker (ADR-132 D9, #808) ────────────────────────────


def test_intentionally_ungated_route_with_rationale_passes() -> None:
    """A route named in INTENTIONALLY_UNGATED with a non-empty rationale
    resolves the finding — the confirmation the rule's own message text
    promises, now with a code path implementing it."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED = {
            "create_census_run": "Read-shaped: INSERTs a tracking row only.",
        }

        @router.post("/runs")
        async def create_census_run():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []


def test_intentionally_ungated_empty_rationale_still_flags() -> None:
    """An empty-string rationale does not count as a confirmation."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED = {
            "create_census_run": "",
        }

        @router.post("/runs")
        async def create_census_run():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "create_census_run" in violations[0]


def test_intentionally_ungated_only_excuses_the_named_route() -> None:
    """A marker entry for one route doesn't blanket-excuse its ungated
    siblings in the same file — the co-location hazard D9 exists to avoid."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED = {
            "create_census_run": "Read-shaped: tracking row only.",
        }

        @router.post("/runs")
        async def create_census_run():
            ...

        @router.post("/baselines/{name}")
        async def create_census_baseline():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "create_census_baseline" in violations[0]


def test_intentionally_ungated_stale_entry_is_flagged() -> None:
    """An INTENTIONALLY_UNGATED key that matches no unguarded mutation route
    in the module is itself a violation — a stale marker looks like coverage
    but is inert (mirrors ADR-152 D4's governed_exclusions orphan check)."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED = {
            "renamed_or_removed_route": "Stale entry.",
        }

        @router.get("/runs")
        async def list_census_runs():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "renamed_or_removed_route" in violations[0]
    assert "stale" in violations[0].lower()


def test_intentionally_ungated_entry_for_already_gated_route_is_stale() -> None:
    """If a route gains a real require_governor gate, its now-redundant
    INTENTIONALLY_UNGATED entry is flagged as stale rather than silently
    tolerated — the marker should track reality, not accumulate history."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED = {
            "create_census_run": "Read-shaped: tracking row only.",
        }

        @router.post("/runs", dependencies=[require_governor])
        async def create_census_run():
            ...
    """)
    violations = ApiAuthChecks.check_sensitive_route_must_be_gated(tree)
    assert len(violations) == 1
    assert "create_census_run" in violations[0]
    assert "stale" in violations[0].lower()


def test_intentionally_ungated_annotated_form_is_recognised() -> None:
    """Real call sites declare INTENTIONALLY_UNGATED with a type annotation
    (`: dict[str, str] = {...}`, an ast.AnnAssign) rather than the plain
    Assign form ROUTER_EXPOSURE uses — both must be recognised."""
    tree = _parse("""
        ROUTER_EXPOSURE = "user-facing"
        router = APIRouter(prefix="/census")

        INTENTIONALLY_UNGATED: dict[str, str] = {
            "create_census_run": "Read-shaped: tracking row only.",
        }

        @router.post("/runs")
        async def create_census_run():
            ...
    """)
    assert ApiAuthChecks.check_sensitive_route_must_be_gated(tree) == []
