# src/body/quality/coverage_candidate_selector.py

"""
Candidate file selection for batch test-coverage remediation (#814).

Extracted from will.self_healing.batch_remediation_service.BatchRemediationService
(ADR-135 D7 predecessor) so file-selection — a pure Body-layer read: coverage
ranking + complexity filtering, no generation, no I/O writes — survives
EnhancedTestGenerator's retirement without dragging the legacy generation
service along as a dependency of its own selection logic.
"""

from __future__ import annotations

from pathlib import Path

from body.quality.coverage_analyzer import CoverageAnalyzer
from body.self_healing.complexity_filter import ComplexityFilter
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger


logger = getLogger(__name__)

_CFG = load_operational_config().coverage


# ID: b4f51cb1-33f0-4fd0-9fb9-51f5f12c5e42
def select_batch_candidates(
    repo_root: Path,
    count: int,
    *,
    max_complexity: str = "MODERATE",
) -> list[tuple[Path, float]]:
    """Return up to `count` src/ files below the coverage threshold.

    Sorted by lowest coverage first (biggest wins), then filtered to files
    simple enough to attempt (ComplexityFilter), matching
    BatchRemediationService's prior selection order exactly: rank all
    below-threshold candidates, filter by complexity, then truncate to
    `count` — not the reverse, which would let complexity filtering silently
    shrink the returned set below what the caller asked for.
    """
    analyzer = CoverageAnalyzer(repo_path=repo_root)
    coverage_data = analyzer.get_module_coverage()
    if not coverage_data:
        return []

    candidates = [
        (repo_root / path, percent)
        for path, percent in coverage_data.items()
        if path.startswith("src/") and percent < _CFG.batch_remediation_threshold_pct
    ]
    candidates.sort(key=lambda item: item[1])

    complexity_filter = ComplexityFilter(max_complexity=max_complexity)
    filtered: list[tuple[Path, float]] = []
    for file_path, coverage in candidates:
        if not file_path.exists():
            continue
        check = complexity_filter.should_attempt(file_path)
        if check["should_attempt"]:
            filtered.append((file_path, coverage))
        else:
            logger.debug(
                "select_batch_candidates: filtered %s: %s",
                file_path,
                check["reason"],
            )

    return filtered[:count]
