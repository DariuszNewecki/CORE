from __future__ import annotations

from cli.route_match import route_matcher


# ID: ed01202e-1014-4936-ae7e-4af5aadb0ac3
def test_route_matcher():
    route = ("db", "migrate")
    matches = route_matcher(route)

    assert matches(["db", "migrate"]) is True
    assert matches(["db", "migrate", "--dry-run"]) is True
    assert matches(["db", "status"]) is False
    assert matches(["db"]) is False
    assert matches([]) is False
