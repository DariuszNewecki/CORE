# infra/scripts/migrations/add_version_updated_at_to_autonomous_proposals.py
"""
Add version (INTEGER NOT NULL DEFAULT 0) and updated_at (TIMESTAMPTZ NOT NULL
DEFAULT now()) to core.autonomous_proposals, then wire up the existing
core.set_updated_at() trigger function to keep updated_at current on every row
update.

core.set_updated_at() is already defined in the schema — this script does NOT
create it.  The trigger creation is guarded by a pg_trigger existence check so
the script is safe to re-run.
"""

import asyncio

from shared.infrastructure.database.session_manager import get_session
from sqlalchemy import text


async def main() -> None:
    print("Starting migration: add version + updated_at to core.autonomous_proposals...")

    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    ALTER TABLE core.autonomous_proposals
                        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    """
                )
            )
            print(
                "  -> Added columns: version INTEGER NOT NULL DEFAULT 0, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
            )

            # CREATE TRIGGER IF NOT EXISTS is PG17+; use a DO block for PG16 compatibility.
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_trigger
                            WHERE tgname = 'trg_autonomous_proposals_updated_at'
                        ) THEN
                            CREATE TRIGGER trg_autonomous_proposals_updated_at
                                BEFORE UPDATE ON core.autonomous_proposals
                                FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
                        END IF;
                    END;
                    $$
                    """
                )
            )
            print("  -> Trigger trg_autonomous_proposals_updated_at ensured.")

    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(main())
