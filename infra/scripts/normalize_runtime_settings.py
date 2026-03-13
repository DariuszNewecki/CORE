#!/usr/bin/env python3
"""
Normalize core.runtime_settings keys from UPPERCASE_UNDERSCORE to dot.notation.

Convention: OLLAMA_REASONER_API_URL -> ollama_reasoner.api_url
            GROK_API_URL            -> grok.api_url
            QDRANT_URL              -> qdrant.url
            REPO_PATH               -> repo.path

Run once. Idempotent — skips keys already in dot-notation.
"""

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def to_dot_notation(key: str) -> str | None:
    """
    Convert UPPER_UNDERSCORE key to dot.notation.
    Returns None if key is already dot-notation or should be skipped.

    Rules:
      - Must be ALL_CAPS_WITH_UNDERSCORES
      - Last segment becomes the property: API_URL -> api_url, MODEL_NAME -> model_name
      - Everything before the last known suffix becomes the prefix
    """
    if "." in key:
        return None  # already dot-notation, skip

    if not re.match(r"^[A-Z][A-Z0-9_]+$", key):
        return None  # mixed case or other format, skip

    known_suffixes = [
        "API_URL", "MODEL_NAME", "API_KEY", "MAX_CONCURRENT",
        "RATE_LIMIT", "COLLECTION_NAME", "URL", "HOST", "PATH",
        "PORT", "TIMEOUT", "KEY", "TOKEN", "SECRET",
    ]

    for suffix in known_suffixes:
        if key.endswith(f"_{suffix}"):
            resource = key[: -(len(suffix) + 1)].lower()
            prop = suffix.lower()
            return f"{resource}.{prop}"

    # No known suffix — lowercase the whole thing with last segment as property
    parts = key.rsplit("_", 1)
    if len(parts) == 2:
        return f"{parts[0].lower()}.{parts[1].lower()}"

    return key.lower().replace("_", ".")


async def migrate() -> None:
    from sqlalchemy import text
    from shared.infrastructure.database.session_manager import get_session

    async with get_session() as session:
        result = await session.execute(
            text("SELECT key, value, is_secret FROM core.runtime_settings ORDER BY key")
        )
        rows = result.fetchall()

    migrations: list[tuple[str, str, str, bool]] = []  # (old, new, value, is_secret)
    skipped: list[str] = []

    for key, value, is_secret in rows:
        new_key = to_dot_notation(key)
        if new_key is None or new_key == key:
            skipped.append(key)
            continue
        migrations.append((key, new_key, value, is_secret))

    if not migrations:
        print("Nothing to migrate.")
        return

    print(f"Keys to migrate: {len(migrations)}")
    print(f"Keys to skip (already dot-notation or unrecognized): {len(skipped)}")
    print()
    for old, new, _, _ in migrations:
        print(f"  {old}  ->  {new}")

    confirm = input("\nApply? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    async with get_session() as session:
        for old, new, value, is_secret in migrations:
            # Insert new key (skip if already exists from a previous partial run)
            await session.execute(
                text("""
                    INSERT INTO core.runtime_settings (key, value, is_secret)
                    VALUES (:key, :value, :is_secret)
                    ON CONFLICT (key) DO NOTHING
                """),
                {"key": new, "value": value, "is_secret": is_secret},
            )
            # Delete old key
            await session.execute(
                text("DELETE FROM core.runtime_settings WHERE key = :key"),
                {"key": old},
            )
        await session.commit()

    print(f"\nDone. {len(migrations)} keys migrated.")
    print("Note: encrypted secrets were NOT migrated (keys with is_secret=true).")
    print("Re-set any secrets via: core-admin secrets set <new.key> --value <value>")


if __name__ == "__main__":
    asyncio.run(migrate())
