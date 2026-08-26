from __future__ import annotations

from api.v1.scout_routes import ScoutRequest


# ID: b3c8961e-cc97-43e0-a928-0f94dfb9e315
def test_ScoutRequest():
    # Test happy path: create a ScoutRequest with a path and default reset
    request = ScoutRequest(path="/tmp/example")

    # Verify the path and reset values
    assert request.path == "/tmp/example"
    assert request.reset is False

    # Test with reset explicitly set to True
    request_with_reset = ScoutRequest(path="/var/log", reset=True)
    assert request_with_reset.path == "/var/log"
    assert request_with_reset.reset is True
