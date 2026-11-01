from __future__ import annotations


# ID: fe297080-adbe-4037-b8ea-c9add8baa359
async def test_project_cognitive_roles():
    from unittest.mock import AsyncMock, MagicMock, patch

    from api.v1.cognitive_role_routes import project_cognitive_roles

    core_context = MagicMock()

    request = MagicMock()
    request.app.state.core_context = core_context

    payload = MagicMock()
    payload.write = True

    result = MagicMock()
    result.ok = True
    result.data = {"roles": ["role-a", "role-b"]}
    result.duration_sec = 0.42

    response = (
        await project_cognitive_roles.__wrapped__(request, payload) if False else None
    )

    with patch(
        "api.v1.cognitive_role_routes.run_project_cognitive_roles",
        new=AsyncMock(return_value=result),
    ) as mock_run:
        response = await project_cognitive_roles(request, payload)

    mock_run.assert_awaited_once_with(core_context, write=True)
    assert response.ok is True
    assert response.data == {"roles": ["role-a", "role-b"]}
    assert response.duration_sec == 0.42
