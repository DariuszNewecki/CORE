"""Tests for ``cli.route_match`` — the pre-bootstrap two-token route matcher."""

from __future__ import annotations

from cli.route_match import route_matcher


def test_matches_exact_two_token_prefix() -> None:
    matches = route_matcher(("runtime", "external-run"))
    assert matches(["runtime", "external-run"])
    assert matches(["runtime", "external-run", "--subject", "x"])


def test_rejects_other_routes_and_short_argv() -> None:
    matches = route_matcher(("runtime", "external-run"))
    assert not matches(["runtime", "external-verify"])
    assert not matches(["runtime"])
    assert not matches([])
    assert not matches(["external-run", "runtime"])


def test_both_dispatch_routes_use_distinct_matchers() -> None:
    from cli.runtime_external_run import matches_route as run_matches
    from cli.runtime_external_verify import matches_route as verify_matches

    assert run_matches(["runtime", "external-run"])
    assert not run_matches(["runtime", "external-verify"])
    assert verify_matches(["runtime", "external-verify"])
    assert not verify_matches(["runtime", "external-run"])
