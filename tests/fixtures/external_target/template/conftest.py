"""Makes ``package`` importable for this template's own native test.

Only ever loaded when pytest is invoked directly against a materialized
copy of this template (a standalone Git repository) -- CORE's own suite
never collects this file; see the ``collect_ignore`` in the parent
``tests/fixtures/external_target/conftest.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
