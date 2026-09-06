"""Minimal native test proving the pristine fixture package works.

Run inside the materialized, disposable copy of this template (a real,
standalone Git repository) -- never as part of CORE's own test suite.
"""

from __future__ import annotations

from package.example import greet
from package.sub.nested import double


def test_greet() -> None:
    assert greet("world") == "Hello, world!"


def test_double() -> None:
    assert double(21) == 42
