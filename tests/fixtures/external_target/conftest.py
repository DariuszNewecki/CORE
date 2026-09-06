"""Keeps the committed template out of CORE's own test collection.

``template/`` is a neutral repo template materialized into disposable Git
repositories by ``materialize.py`` -- it is never meant to run as part of
CORE's own suite (its own ``tests/test_example.py`` and ``conftest.py``
are for the *materialized copy*, not this checkout).
"""

from __future__ import annotations


collect_ignore = ["template"]
