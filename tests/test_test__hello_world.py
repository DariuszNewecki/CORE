"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/test.py
- Symbol: hello_world
- Status: verified_in_sandbox
- Generated: 2026-01-11 10:35:30
"""

import pytest
from test import hello_world

# Detected return type: str

def test_hello_world_returns_correct_string():
    assert hello_world() == "Hello, CORE!"
