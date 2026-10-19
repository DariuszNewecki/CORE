# src/mind/logic/_throwaway_db_probe.py
"""THROWAWAY (do not merge): mind reaching the database, which
architecture.mind.no_database_access forbids."""

from __future__ import annotations

from shared.infrastructure.database.session_manager import get_session


_SESSION = get_session
