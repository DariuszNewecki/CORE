# tests/helpers/db_identity_probe_plugin.py
"""Child-run pytest plugin for the #941 database-identity guard regression test.

Simulates a misconfigured ``.env.test``: rewrites ``DATABASE_URL`` to name the
database in ``CORE_DB_IDENTITY_PROBE_DATABASE`` after pytest-dotenv has loaded
``.env.test`` (its hook is ``tryfirst``) and before the root conftest imports
``shared.config`` (pytest's own conftest loading is ``trylast``), so ``Settings``
resolves the rewritten URL exactly as it would a bad file.

The probe name must be a database that does not exist, so even a broken guard
could only fail to connect — never reach live data.
"""

from __future__ import annotations

import os

from sqlalchemy.engine import make_url


# ID: f45a8781-d711-4e3b-9ffd-1ac71ac7a552
def pytest_load_initial_conftests(early_config, parser, args) -> None:
    probe = os.environ["CORE_DB_IDENTITY_PROBE_DATABASE"]
    url = make_url(os.environ["DATABASE_URL"]).set(database=probe)
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
