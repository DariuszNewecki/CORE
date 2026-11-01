from __future__ import annotations

from api.main import create_app


# ID: 80bb162f-534b-4895-8971-fe146c690944
def test_create_app():
    app = create_app()

    assert app.title == "CORE OEM API"
    assert app.openapi_url == "/v1/openapi.json"

    health_route = next(
        (r for r in app.routes if getattr(r, "path", None) == "/health"), None
    )
    assert health_route is not None
    assert health_route.endpoint() == {"status": "ok"}

    schema = app.openapi()
    assert schema["info"]["x-stability-policy"] == (
        "https://github.com/DariuszNewecki/CORE/blob/main/.specs/DECISIONS.md"
    )
