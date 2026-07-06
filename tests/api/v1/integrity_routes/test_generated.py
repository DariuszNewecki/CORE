from __future__ import annotations

from api.v1.integrity_routes import IntegrityRequest


# ID: c0369889-e6fe-41f9-961f-b2dfd1272643
def test_IntegrityRequest():
    # Test default construction
    request = IntegrityRequest()
    assert request.label == "default"

    # Test construction with explicit label
    request = IntegrityRequest(label="custom_label")
    assert request.label == "custom_label"

    # Test empty body equivalence (label defaults to "default")
    request = IntegrityRequest()
    assert request.label == "default"
