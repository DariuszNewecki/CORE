# src/core/db/models.py
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ID: a19218aa-2df2-4c22-a203-f9ddee5531a9
class Base(DeclarativeBase):
    pass


# ID: 81d40765-42f5-4302-8536-ded11800704b
class LlmResource(Base):
    """
    Minimal model used by tests to register available LLM backends.
    """

    __tablename__ = "llm_resources"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    provided_capabilities: Mapped[List[str]] = mapped_column(JSON)
    env_prefix: Mapped[str] = mapped_column(String)
    performance_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


# ID: f03ba1d4-443a-47ce-9599-ec0376ddbb1c
class CognitiveRole(Base):
    """
    Minimal model used by tests to map app roles -> required capabilities.
    """

    __tablename__ = "cognitive_roles"

    role: Mapped[str] = mapped_column(String, primary_key=True)
    required_capabilities: Mapped[List[str]] = mapped_column(JSON)
