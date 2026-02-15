# src/body/services/cim/diff.py
# ID: c36677be-3972-44fa-a3da-f1b96f50cf7c

"""
CIM Diff Engine - Compare census runs.
"""

from __future__ import annotations

from shared.logger import getLogger

from .models import CensusDelta, CensusDiff, HotspotChange, RepoCensus


logger = getLogger(__name__)


# ID: 9e531ca2-1356-43dd-b28a-88e9c7a9bffb
class DiffEngine:
    """Generate diffs between census runs."""

    # ID: 9cc0cac7-7efc-4317-b28c-84f24930cfaa
    def compute_diff(
        self,
        baseline: RepoCensus,
        current: RepoCensus,
        baseline_name: str | None = None,
    ) -> CensusDiff:
        """
        Compute diff: current - baseline.

        Positive deltas = increase
        Negative deltas = decrease
        """
        diff = CensusDiff(
            baseline_name=baseline_name,
            baseline_commit=baseline.repo.git_commit,
            current_commit=current.repo.git_commit,
            execution_surfaces=self._delta(
                baseline.summary.execution_surfaces_count,
                current.summary.execution_surfaces_count,
            ),
            mutation_surfaces_total=self._delta(
                baseline.summary.mutation_surfaces_count_total,
                current.summary.mutation_surfaces_count_total,
            ),
            write_ephemeral=self._delta(
                baseline.summary.write_ephemeral_count,
                current.summary.write_ephemeral_count,
            ),
            write_production=self._delta(
                baseline.summary.write_production_count,
                current.summary.write_production_count,
            ),
            write_prohibited_zone=self._delta(
                baseline.summary.write_prohibited_zone_count,
                current.summary.write_prohibited_zone_count,
            ),
        )

        # By type
        all_types = set(baseline.summary.mutation_surfaces_by_type.keys()) | set(
            current.summary.mutation_surfaces_by_type.keys()
        )
        for mut_type in all_types:
            old_val = baseline.summary.mutation_surfaces_by_type.get(mut_type, 0)
            new_val = current.summary.mutation_surfaces_by_type.get(mut_type, 0)
            diff.by_type[mut_type] = self._delta(old_val, new_val)

        # By lane
        all_lanes = set(baseline.summary.mutation_surfaces_by_lane.keys()) | set(
            current.summary.mutation_surfaces_by_lane.keys()
        )
        for lane in all_lanes:
            old_val = baseline.summary.mutation_surfaces_by_lane.get(lane, 0)
            new_val = current.summary.mutation_surfaces_by_lane.get(lane, 0)
            diff.by_lane[lane] = self._delta(old_val, new_val)

        # Hotspot changes
        self._compute_hotspot_changes(baseline, current, diff)

        # Critical: new prohibited writes
        diff.new_prohibited_writes = max(
            0,
            current.summary.write_prohibited_zone_count
            - baseline.summary.write_prohibited_zone_count,
        )

        return diff

    def _delta(self, old_value: int, new_value: int) -> CensusDelta:
        """Compute delta with percent change."""
        delta = new_value - old_value
        percent = None
        if old_value > 0:
            percent = (delta / old_value) * 100.0

        return CensusDelta(
            old_value=old_value,
            new_value=new_value,
            delta=delta,
            percent_change=percent,
        )

    def _compute_hotspot_changes(
        self, baseline: RepoCensus, current: RepoCensus, diff: CensusDiff
    ):
        """Detect hotspot additions/removals/changes."""
        # Build hotspot maps
        baseline_hotspots = {h.path: h for h in baseline.summary.top_mutation_files}
        current_hotspots = {h.path: h for h in current.summary.top_mutation_files}

        # Added hotspots
        for path in current_hotspots.keys() - baseline_hotspots.keys():
            diff.hotspots_added.append(
                HotspotChange(
                    path=path,
                    old_count=None,
                    new_count=current_hotspots[path].mutation_count,
                    delta=current_hotspots[path].mutation_count,
                    status="added",
                )
            )

        # Removed hotspots
        for path in baseline_hotspots.keys() - current_hotspots.keys():
            diff.hotspots_removed.append(
                HotspotChange(
                    path=path,
                    old_count=baseline_hotspots[path].mutation_count,
                    new_count=None,
                    delta=-baseline_hotspots[path].mutation_count,
                    status="removed",
                )
            )

        # Changed hotspots
        for path in baseline_hotspots.keys() & current_hotspots.keys():
            old_count = baseline_hotspots[path].mutation_count
            new_count = current_hotspots[path].mutation_count
            delta = new_count - old_count

            if delta != 0:
                status = "increased" if delta > 0 else "decreased"
                diff.hotspots_changed.append(
                    HotspotChange(
                        path=path,
                        old_count=old_count,
                        new_count=new_count,
                        delta=delta,
                        status=status,
                    )
                )
