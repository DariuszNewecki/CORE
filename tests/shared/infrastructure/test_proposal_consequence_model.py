# tests/shared/infrastructure/test_proposal_consequence_model.py
"""Structural tests for ProposalConsequence SQLAlchemy model (ADR-016 D1).

Verifies that the model:
- Registers in Base.metadata so create_all() produces the table
- Has the correct tablename, schema, and column set
- Exposes log_retention_months on SystemConfig (paired ADR-052 model update)
"""

from __future__ import annotations

from sqlalchemy import inspect

from shared.infrastructure.database.models import (
    Base,
    ProposalConsequence,
    SystemConfig,
)


# ID: 9845c1da-8201-4692-ab38-ac2ca8c489b7
def test_proposal_consequence_registered_in_metadata() -> None:
    """ProposalConsequence must appear in Base.metadata so create_all includes it."""
    assert "core.proposal_consequences" in Base.metadata.tables


# ID: d13d94f4-bc91-47e2-a0d7-ebfb0ab2d53b
def test_proposal_consequence_columns() -> None:
    """ProposalConsequence must expose all columns from the SQL schema."""
    mapper = inspect(ProposalConsequence)
    col_names = {col.key for col in mapper.columns}
    required = {
        "proposal_id",
        "recorded_at",
        "pre_execution_sha",
        "post_execution_sha",
        "files_changed",
        "findings_resolved",
        "authorized_by_rules",
        "declared_production",
    }
    assert required.issubset(col_names)


def test_proposal_consequence_primary_key() -> None:
    """proposal_id is the primary key."""
    mapper = inspect(ProposalConsequence)
    pk_cols = {col.key for col in mapper.primary_key}
    assert pk_cols == {"proposal_id"}


def test_system_config_has_log_retention_months() -> None:
    """SystemConfig must expose log_retention_months (ADR-052 pairing)."""
    mapper = inspect(SystemConfig)
    col_names = {col.key for col in mapper.columns}
    assert "log_retention_months" in col_names
