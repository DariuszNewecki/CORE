from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


# ID: 4345a02a-1038-4d1b-aa81-b2469dd907ee
def test_render_openapi_document():
    from api.openapi_document import render_openapi_document

    fake_spec = {"openapi": "3.1.0", "paths": {"/health": {"get": {}}}}
    fake_app = MagicMock()
    fake_app.openapi.return_value = fake_spec

    with patch("api.main.create_app", return_value=fake_app) as mock_create_app:
        result = render_openapi_document()

    mock_create_app.assert_called_once_with()
    fake_app.openapi.assert_called_once_with()

    expected = json.dumps(fake_spec, indent=2, ensure_ascii=False) + "\n"
    assert result == expected
    assert result.endswith("\n")
    assert json.loads(result) == fake_spec
