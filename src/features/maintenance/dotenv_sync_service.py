# src/features/maintenance/dotenv_sync_service.py

"""Provides functionality for the dotenv_sync_service module."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.config import settings
from shared.infrastructure.database.models import RuntimeSetting
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: b4e0cca2-7956-4ee9-80bc-e36aca3bf0f5
async def run_dotenv_sync(dry_run: bool):
    """
    Reads variables defined in runtime_requirements.yaml from the environment/.env
    and upserts them into the core.runtime_settings table.
    """
    logger.info("Synchronizing .env configuration to database...")
    try:
        runtime_reqs = settings.load("mind.config.runtime_requirements")
        variables_to_sync = runtime_reqs.get("variables", {})
    except FileNotFoundError as e:
        logger.error("Cannot find runtime_requirements policy: %s", e)
        return
    settings_to_upsert: list[dict[str, Any]] = []
    for key, config in variables_to_sync.items():
        value = getattr(settings, key, None)
        if value is None:
            value_str = None
        elif isinstance(value, bool):
            value_str = str(value).lower()
        else:
            value_str = str(value)
        is_secret = config.get("source") == "secret" or "_KEY" in key or "_TOKEN" in key
        settings_to_upsert.append(
            {
                "key": key,
                "value": value_str,
                "description": config.get("description"),
                "is_secret": is_secret,
            }
        )
    if dry_run:
        logger.info("-- DRY RUN: The following settings would be synced --")
        for setting in settings_to_upsert:
            display_value = (
                "********"
                if setting["is_secret"] and setting["value"]
                else str(setting["value"])
            )
            logger.info(
                "Plan: Key=%s | Value=%s | Secret=%s",
                setting["key"],
                display_value,
                setting["is_secret"],
            )
        return
    try:
        async with get_session() as session:
            async with session.begin():
                stmt = pg_insert(RuntimeSetting).values(settings_to_upsert)
                update_dict = {
                    "value": stmt.excluded.value,
                    "description": stmt.excluded.description,
                    "is_secret": stmt.excluded.is_secret,
                    "last_updated": func.now(),
                }
                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["key"], set_=update_dict
                )
                await session.execute(upsert_stmt)
        logger.info(
            "Successfully synchronized %d settings to the database.",
            len(settings_to_upsert),
        )
    except Exception as e:
        logger.error("Database sync failed: %s", e, exc_info=True)
        # Note: Logic layer should generally raise exceptions or return status,
        # but complying with existing pattern where return is void.
