# src/api/openapi_document.py

"""
The committed OpenAPI document — CORE's public API contract as a file.

ADR-087 D9 (amended 2026-10-03): the authoritative OpenAPI specification of
CORE's public API lives in CORE. The running daemon serves it live; this module
renders the same document for the committed copy at ``docs/reference/openapi.json``
(written by ``core-admin docs generate``), so consumers such as core-cli can read
and test against the contract without running CORE.

CONSTITUTIONAL:
- Pure rendering: builds the app via ``create_app()`` and serialises
  ``app.openapi()``. No I/O; the caller writes through FileHandler.
"""

from __future__ import annotations

import json


OPENAPI_DOCUMENT = "docs/reference/openapi.json"


# ID: a13f1bcc-df55-40f4-9065-cd203144ef7b
def render_openapi_document() -> str:
    """Render CORE's public OpenAPI document as stable, indented JSON.

    Only routes published in the schema appear; routes marked
    ``include_in_schema=False`` are internal and absent (ADR-087).
    """
    from api.main import create_app

    spec = create_app().openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
