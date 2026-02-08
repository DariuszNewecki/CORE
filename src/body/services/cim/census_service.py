# src/body/services/cim/census_service.py
# ID: body.services.cim.census_service

"""
Census Service - Orchestrates CIM-0 repository census.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from pathlib import Path

from shared.logger import getLogger

from .models import CensusSummary, MutationHotspot, RepoCensus, RepoCensusMetadata
from .scanners import (
    _should_skip_path,
    extract_cli_entrypoints,
    scan_architectural_signals,
    scan_execution_surfaces,
    scan_git_metadata,
    scan_mutation_surfaces,
    scan_tree_stats,
)


logger = getLogger(__name__)


# ID: 0b9a7f04-a0b2-438e-89d1-c0690c8fe2a4
class CensusService:
    """
    Read-only census orchestrator for CIM-0.

    Never mutates the target repository.
    Produces deterministic RepoCensus artifact.
    """

    # ID: 062ee433-9e2b-4498-b8d2-fcc5b64150a7
    def run_census(self, repo_path: Path) -> RepoCensus:
        """
        Execute full CIM-0 census on target repository.

        Returns:
            RepoCensus artifact with all collected data and actionable intelligence
        """
        logger.info("Starting CIM-0 census: %s", repo_path)

        metadata = RepoCensusMetadata(
            run_id=str(uuid.uuid4()),
            core_version="2.0.0",
        )

        repo_info = scan_git_metadata(repo_path)
        tree_stats = scan_tree_stats(repo_path)
        signals = scan_architectural_signals(repo_path)
        exec_surfaces, exec_errors = scan_execution_surfaces(repo_path)
        mut_surfaces, mut_errors = scan_mutation_surfaces(repo_path)

        all_errors = exec_errors + mut_errors
        all_errors.sort(key=lambda e: e.path)

        summary = self._generate_summary(
            repo_path, exec_surfaces, mut_surfaces, all_errors
        )

        census = RepoCensus(
            metadata=metadata,
            repo=repo_info,
            tree=tree_stats,
            signals=signals,
            summary=summary,
            execution_surfaces=exec_surfaces,
            mutation_surfaces=mut_surfaces,
            errors=all_errors,
        )

        logger.info(
            "Census complete: %d files, %d execution surfaces, %d mutation surfaces (%d allowlisted), %d errors",
            tree_stats.total_files,
            len(exec_surfaces),
            len(mut_surfaces),
            summary.allowlisted_surfaces_count,
            len(all_errors),
        )

        return census

    def _generate_summary(
        self, repo_path: Path, exec_surfaces, mut_surfaces, errors
    ) -> CensusSummary:
        """Generate aggregated statistics with actionable intelligence."""
        by_type: dict[str, int] = defaultdict(int)
        by_operation: dict[str, int] = defaultdict(int)
        by_lane: dict[str, int] = defaultdict(int)

        # Write zone classification
        write_ephemeral = 0
        write_production = 0
        write_prohibited = 0
        write_unknown = 0

        allowlisted_count = 0

        for surface in mut_surfaces:
            by_type[surface.type] += 1
            by_operation[surface.operation] += 1

            if surface.lane:
                by_lane[surface.lane] += 1

            if surface.allowlisted:
                allowlisted_count += 1

            # Classify writes by zone
            if surface.operation == "write" and surface.write_zone:
                if surface.write_zone == "ephemeral":
                    write_ephemeral += 1
                elif surface.write_zone == "production":
                    write_production += 1
                elif surface.write_zone == "prohibited":
                    write_prohibited += 1
                elif surface.write_zone == "unknown":
                    write_unknown += 1

        hotspots = self._find_mutation_hotspots(mut_surfaces, limit=10)
        cli_entrypoints = extract_cli_entrypoints(repo_path)

        path_classes: dict[str, int] = defaultdict(int)
        for py_file in repo_path.rglob("*.py"):
            if _should_skip_path(py_file, repo_path):
                continue
            rel_path = py_file.relative_to(repo_path)
            if len(rel_path.parts) > 0:
                prefix = rel_path.parts[0]
                path_classes[prefix] += 1

        return CensusSummary(
            execution_surfaces_count=len(exec_surfaces),
            mutation_surfaces_count_total=len(mut_surfaces),
            write_ephemeral_count=write_ephemeral,
            write_production_count=write_production,
            write_prohibited_zone_count=write_prohibited,
            write_unknown_count=write_unknown,
            mutation_surfaces_by_type=dict(sorted(by_type.items())),
            mutation_surfaces_by_operation=dict(sorted(by_operation.items())),
            top_mutation_files=hotspots,
            allowlisted_surfaces_count=allowlisted_count,
            mutation_surfaces_by_lane=dict(sorted(by_lane.items())),
            cli_entrypoints=cli_entrypoints,
            errors_count=len(errors),
            path_class_counts=dict(sorted(path_classes.items())),
        )

    def _find_mutation_hotspots(
        self, surfaces: list, limit: int = 10
    ) -> list[MutationHotspot]:
        """Rank files by mutation surface density."""
        by_file: dict[str, dict] = defaultdict(
            lambda: {
                "count": 0,
                "types": defaultdict(int),
                "operations": defaultdict(int),
            }
        )

        for s in surfaces:
            by_file[s.path]["count"] += 1
            by_file[s.path]["types"][s.type] += 1
            by_file[s.path]["operations"][s.operation] += 1

        hotspots = []
        for path, data in by_file.items():
            dominant_type = max(data["types"].items(), key=lambda x: x[1])[0]
            dominant_op = max(data["operations"].items(), key=lambda x: x[1])[0]
            hotspots.append(
                MutationHotspot(
                    path=path,
                    mutation_count=data["count"],
                    dominant_type=dominant_type,
                    dominant_operation=dominant_op,
                )
            )

        return sorted(hotspots, key=lambda x: x.mutation_count, reverse=True)[:limit]
