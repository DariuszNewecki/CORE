"""Tests for CrawlService.

2026-06-07 (#572 Cat B batch 20): the autogen vintage of this file was
an unconditional stub — it referenced ``CrawlService`` and ``Path``
without importing either (NameError on every test under pytest),
relied on ``unittest.TestCase`` ``setUp``, and the test bodies were
just method invocations followed by ``# Add assertions to verify``
comments. One test even called ``self.assertIsNotEmpty(...)``, which
isn't a real ``unittest.TestCase`` method.

The scan probe registered the file as 0 PASS / 0 FAIL because the
class name (``CrawlServiceTest``) uses the ``*Test`` suffix pattern
that the probe runner doesn't pick up — pytest with unittest
discovery would have surfaced the NameErrors. Either way the file was
dead.

Replaced with a single import-smoke test. Deeper behavioural coverage
of crawl runs requires a real DB session + repo and belongs in the
integration suite, not in an autogen unit test.
"""

from __future__ import annotations


def test_crawl_service_imports_cleanly():
    """The canonical CrawlService is exported from
    ``body.services.crawl_service``. This smoke test pins the import
    surface so a refactor that breaks the public name fails loudly
    instead of silently."""
    from body.services.crawl_service import CrawlService

    assert isinstance(CrawlService, type)
