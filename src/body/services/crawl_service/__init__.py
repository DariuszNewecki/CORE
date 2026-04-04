# src/body/services/crawl_service/__init__.py
# crawl_service/__init__.py
"""
Package split from crawl_service.py.
"""

from __future__ import annotations

from .main_module import CrawlService, logger
from .symbol_processing import _CallGraphExtractor, _detect_layer, _sha256
