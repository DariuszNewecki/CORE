#!/usr/bin/env python3
"""
Print the fresh-install migration ledger seed block to stdout (ADR-162 D9).

Called by ``infra/scripts/reset_test_db.sh`` after the ``pg_dump`` step so
``schema.sql`` ends with one ``INSERT INTO core._migrations`` per manifest
entry, in manifest order. ``tests/shared/infrastructure/test_schema_ledger_seed.py``
proves the committed block equals this output byte for byte.

Rendering lives in ``shared.infrastructure.repositories.db.ledger_seed``;
this script is only the terminal surface for it. Run from the repository
root with the project environment on PATH::

    poetry run python infra/scripts/render_ledger_seed.py
"""

from __future__ import annotations

import sys

from shared.infrastructure.repositories.db.ledger_seed import render_ledger_seed
from shared.infrastructure.repositories.db.manifest import load_manifest


def main() -> int:
    sys.stdout.write(render_ledger_seed(load_manifest().order))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
