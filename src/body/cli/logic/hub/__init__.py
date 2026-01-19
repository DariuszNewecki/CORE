# src/body/cli/logic/hub/__init__.py
"""
Central Hub Package.
Traffic controller for CORE tool discovery.
"""

from __future__ import annotations

# We export the app for the main CLI registry
# and the search logic for the 'search' command group
from .app import hub_app, hub_search_cmd


__all__ = ["hub_app", "hub_search_cmd"]
