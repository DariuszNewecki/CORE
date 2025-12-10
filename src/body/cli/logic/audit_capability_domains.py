# src/body/cli/logic/audit_capability_domains.py
"""
Provides functionality for the audit_capability_domains module.
"""

from __future__ import annotations

import typer
from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session


async def _audit_queries(limit: int):
    """Audit capabilities database for data quality issues,
    returning counts of total capabilities and lists of keys with
    zero tags, multiple primary domains, legacy domain mismatches,
    and inactive domain tags."""
    async with get_session() as session:
        total = (
            await session.execute(
                text("select count(*) as c from body.services.capabilities")
            )
        ).scalar_one()

        zero_tags_stmt = text(
            """
            select c.key
            from body.services.capabilities c
            where not exists (
              select 1 from core.capability_domains d
              where d.capability_key = c.key
            )
            limit :lim
            """
        ).bindparams(lim=limit)
        zero_tags_rows = (await session.execute(zero_tags_stmt)).scalars().all()

        multi_primary_stmt = text(
            """
            select capability_key
            from core.capability_domains
            group by capability_key
            having sum(case when is_primary then 1 else 0 end) > 1
            limit :lim
            """
        ).bindparams(lim=limit)
        multi_primary_rows = (await session.execute(multi_primary_stmt)).scalars().all()

        legacy_mismatch_stmt = text(
            """
            select c.key
            from body.services.capabilities c
            where c.domain is not null
              and not exists (
                select 1 from core.capability_domains d
                where d.capability_key = c.key
                  and d.domain_key = c.domain
              )
            limit :lim
            """
        ).bindparams(lim=limit)
        legacy_mismatch_rows = (
            (await session.execute(legacy_mismatch_stmt)).scalars().all()
        )

        inactive_domain_tags_stmt = text(
            """
            select distinct d.capability_key
            from core.capability_domains d
            join core.domains dm on dm.key = d.domain_key
            where dm.status != 'active'
            limit :lim
            """
        ).bindparams(lim=limit)
        inactive_tag_rows = (
            (await session.execute(inactive_domain_tags_stmt)).scalars().all()
        )

        return (
            total,
            zero_tags_rows,
            multi_primary_rows,
            legacy_mismatch_rows,
            inactive_tag_rows,
        )


# ID: a2d0d438-253f-49ba-82be-10eb2a2a7749
def audit_capability_domains(
    limit: int = typer.Option(
        20, "--limit", help="Max sample keys to show for each finding"
    ),
):
    """Audit capability domains for common tagging issues and display findings with sample keys."""
    total, zero_tags, multi_primary, legacy_mismatch, inactive_tags = typer.run(
        _audit_queries, limit
    )

    typer.echo(f"Total capabilities: {total}")
    typer.echo(f"Zero tags: {len(zero_tags)}  {zero_tags}")
    typer.echo(f"Multiple primary tags: {len(multi_primary)}  {multi_primary}")
    typer.echo(
        f"Legacy domain not among tags: {len(legacy_mismatch)}  {legacy_mismatch}"
    )
    typer.echo(f"Tags on INACTIVE domains: {len(inactive_tags)}  {inactive_tags}")
