# src/will/agents/conversational/__init__.py

"""
Conversational agent package for end-user natural language interaction with CORE.
"""

from __future__ import annotations

from .agent import ConversationalAgent
from .factory import create_conversational_agent


__all__ = ["ConversationalAgent", "create_conversational_agent"]
