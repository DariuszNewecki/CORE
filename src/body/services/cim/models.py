# src/body/services/cim/models.py
# ID: body.services.cim.models

"""
RepoCensus v1.0.0 Schema - CIM-0 artifact contract.
Enhanced with actionable intelligence for governance.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ID: 40e3aecd-2649-449a-92f3-5c2e5ef3a79e
class RepoCensusMetadata(BaseModel):
    """Metadata about the census run."""

    run_id: str = Field(..., description="Unique identifier for this census run")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    core_version: str = Field(..., description="CORE version that generated this")
    schema_id: str = Field(
        default="core.cim.repo_census", description="Schema identifier"
    )
    schema_version: str = Field(default="1.0.0", description="Schema version")


# ID: 3844eacd-ff27-4568-87d1-609915ebd20e
class RepoInfo(BaseModel):
    """Basic repository information."""

    root_path: str
    git_remote: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None


# ID: 774e0c43-0527-4030-a416-a80fb61b4233
class TreeStats(BaseModel):
    """File tree statistics."""

    total_files: int
    total_directories: int
    extensions: dict[str, int] = Field(
        default_factory=dict, description="Count by file extension (normalized)"
    )
    top_level_dirs: list[str] = Field(
        default_factory=list, description="Sorted list of top-level directories"
    )


# ID: 61589ef8-f460-43d9-80fc-84eb14192032
class ArchitecturalSignals(BaseModel):
    """Detected architectural markers."""

    has_src: bool = False
    has_intent: bool = False
    has_sql: bool = False
    has_tests: bool = False
    has_docs: bool = False
    dependency_files: list[str] = Field(
        default_factory=list,
        description="Found dependency descriptors (pyproject.toml, etc.)",
    )


# ID: ae68ed70-ae76-4b79-bd44-03a1d0ffe474
class ExecutionSurface(BaseModel):
    """Detected entry point."""

    path: str
    type: str  # "cli_entrypoint" | "main_block" | "service_app"
    line: int | None = None


# ID: a6f7acc8-0c8f-462a-8cc3-a8ca6691b756
class MutationSurface(BaseModel):
    """Detected mutation capability."""

    path: str
    type: str  # "filesystem_read" | "filesystem_write" | "subprocess" | "network" | "database"
    operation: str  # "read" | "write" | "execute" | "connect" | "unknown"
    line: int
    detail: str | None = None
    write_zone: str | None = Field(
        None, description="For writes: ephemeral|production|prohibited|unknown"
    )
    lane: str | None = Field(
        None,
        description="Architectural lane (body|mind|will|shared|features|tests|scripts|other)",
    )
    allowlisted: bool = Field(False, description="Known-safe pattern")


# ID: 5bfdd462-3360-4ed6-b3ba-42d08934dbe0
class CensusError(BaseModel):
    """Non-fatal error encountered during census."""

    path: str
    error_type: str
    message: str


# ID: bd8be2b1-50ea-4f03-bd3e-3e3f2c5f2de9
class MutationHotspot(BaseModel):
    """File with high mutation surface density."""

    path: str
    mutation_count: int
    dominant_type: str
    dominant_operation: str


# ID: 184e34d1-cdfc-400f-bb41-6d84401766ca
class CensusSummary(BaseModel):
    """
    Aggregated statistics for quick consumption.

    Prevents consumers from parsing massive arrays.
    Provides actionable intelligence for governance.
    """

    # Basic counts
    execution_surfaces_count: int = 0
    mutation_surfaces_count_total: int = 0

    # Write classification (honest naming)
    write_ephemeral_count: int = Field(
        0, description="Writes to var/, cache/, temp/, scripts/, work/"
    )
    write_production_count: int = Field(
        0, description="Writes to src/, tests/, sql/, docs/ (governed zones)"
    )
    write_prohibited_zone_count: int = Field(
        0, description="Writes to .intent/constitution/** etc."
    )
    write_unknown_count: int = Field(0, description="Writes to unclassified zones")

    # Mutation breakdown
    mutation_surfaces_by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count by mutation type (filesystem_read, filesystem_write, etc.)",
    )
    mutation_surfaces_by_operation: dict[str, int] = Field(
        default_factory=dict,
        description="Count by operation (read, write, execute, connect, unknown)",
    )

    # Hotspots
    top_mutation_files: list[MutationHotspot] = Field(
        default_factory=list, description="Top 10 files by mutation surface density"
    )

    # Allowlist
    allowlisted_surfaces_count: int = Field(
        0, description="Known-safe mutation surfaces"
    )

    # Lane-aware
    mutation_surfaces_by_lane: dict[str, int] = Field(
        default_factory=dict, description="Mutations by architectural lane"
    )

    # CLI entrypoints
    cli_entrypoints: list[str] = Field(
        default_factory=list, description="Installed console_scripts from packaging"
    )

    # Errors
    errors_count: int = 0

    # Path classification
    path_class_counts: dict[str, int] = Field(
        default_factory=dict,
        description="File counts by path prefix (src/, tests/, .intent/, etc.)",
    )


# ID: b42cf792-af21-4de2-8553-5e73063e6cb8
class RepoCensus(BaseModel):
    """
    Complete repository census artifact.

    This is the canonical CIM-0 output format.
    All lists are sorted for determinism.
    """

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    metadata: RepoCensusMetadata
    repo: RepoInfo
    tree: TreeStats
    signals: ArchitecturalSignals
    summary: CensusSummary
    execution_surfaces: list[ExecutionSurface] = Field(default_factory=list)
    mutation_surfaces: list[MutationSurface] = Field(default_factory=list)
    errors: list[CensusError] = Field(default_factory=list)


# ID: 4c987cf7-6e4d-4d7f-af26-ef12ea31b63d
class CensusBaseline(BaseModel):
    """Named baseline for comparison."""

    name: str
    snapshot_file: str
    git_commit: str | None = None
    created_at: datetime


# ID: 99459a02-2a63-43cc-a538-fa7d11c18ec4
class BaselineRegistry(BaseModel):
    """Registry of named baselines."""

    baselines: dict[str, CensusBaseline] = Field(default_factory=dict)


# ID: 17385b61-4a32-49cc-8e1f-571d1586d6fa
class CensusDelta(BaseModel):
    """Numeric delta for a single metric."""

    old_value: int
    new_value: int
    delta: int
    percent_change: float | None = None


# ID: a23a9b82-5769-489f-a026-3c23fb132a50
class HotspotChange(BaseModel):
    """Change in a mutation hotspot."""

    path: str
    old_count: int | None
    new_count: int | None
    delta: int
    status: Literal["added", "removed", "increased", "decreased", "unchanged"]


# ID: 397c268a-2674-4638-823d-6cc7a5acc71e
class CensusDiff(BaseModel):
    """
    Diff between two census runs.

    All deltas use convention: new - old
    Positive = increase, negative = decrease
    """

    baseline_name: str | None = None
    baseline_commit: str | None = None
    current_commit: str | None = None

    # Execution surfaces
    execution_surfaces: CensusDelta

    # Mutation totals
    mutation_surfaces_total: CensusDelta
    write_ephemeral: CensusDelta
    write_production: CensusDelta
    write_prohibited_zone: CensusDelta

    # By type
    by_type: dict[str, CensusDelta] = Field(default_factory=dict)

    # By lane
    by_lane: dict[str, CensusDelta] = Field(default_factory=dict)

    # Hotspot changes
    hotspots_added: list[HotspotChange] = Field(default_factory=list)
    hotspots_removed: list[HotspotChange] = Field(default_factory=list)
    hotspots_changed: list[HotspotChange] = Field(default_factory=list)

    # Critical changes
    new_prohibited_writes: int = 0


# ID: 71cb6841-ec4a-4394-9348-95bf084416e7
class Finding(BaseModel):
    """Policy evaluation result."""

    id: str
    severity: Literal["BLOCK", "HIGH", "MEDIUM", "LOW", "INFO"]
    rule: str
    evidence: str
    recommendation: str
    links: list[str] = Field(default_factory=list)


# ID: 7ad0161f-8549-4c69-bf9d-cf8a19bcca1b
class PolicyEvaluation(BaseModel):
    """Result of evaluating diff against thresholds."""

    findings: list[Finding] = Field(default_factory=list)
    blocking_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    @property
    # ID: 3b2ee9a5-d466-45f1-9a2d-edde3dd82759
    def has_blocking(self) -> bool:
        return self.blocking_count > 0

    @property
    # ID: c497a576-cfa2-43c4-b3c6-548449a7d068
    def exit_code(self) -> int:
        """Exit code for CI integration."""
        if self.blocking_count > 0:
            return 10
        if self.high_count > 0 or self.medium_count > 0:
            return 2
        return 0
