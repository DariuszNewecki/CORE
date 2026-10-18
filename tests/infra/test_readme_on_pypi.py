"""README.md is the PyPI long description (pyproject `readme`), and pypi.org
does not rewrite relative links: `docs/what-core-does.md` became a 404 under
pypi.org/project/core-runtime/ (#1154, proof run 3)."""

from __future__ import annotations

import re
from pathlib import Path


README = Path(__file__).resolve().parents[2] / "README.md"
_LINK = re.compile(r"\]\(([^)\s]+)\)")


def test_every_readme_link_is_absolute() -> None:
    targets = _LINK.findall(README.read_text(encoding="utf-8"))
    assert targets, "no links found; the pattern no longer matches the README"
    relative = [t for t in targets if not t.startswith(("https://", "http://", "#"))]
    assert relative == [], f"relative links 404 on pypi.org: {relative}"
