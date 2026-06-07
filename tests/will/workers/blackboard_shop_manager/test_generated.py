"""Tests for BlackboardShopManager.

2026-06-07 (#572 Cat B batch 19): converted from unittest.TestCase
``setUp`` to a pytest fixture. The autogen vintage relied on the
unittest setUp lifecycle, which our direct-invocation probe runner
doesn't honour (pytest itself would, but the test was clearly a
single-instance shape better expressed as a fixture). One smoke test
preserved.
"""

from __future__ import annotations

import pytest

from will.workers.blackboard_shop_manager import BlackboardShopManager


@pytest.fixture
def shop_manager() -> BlackboardShopManager:
    return BlackboardShopManager()


def test_initialization(shop_manager: BlackboardShopManager) -> None:
    """BlackboardShopManager instantiates with no args and is an instance
    of its own class — the basic import + construction smoke check."""
    assert isinstance(shop_manager, BlackboardShopManager)
