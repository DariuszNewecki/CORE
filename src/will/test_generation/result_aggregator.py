# src/will/test_generation/result_aggregator.py

"""
TestResultAggregator - Formats and packages generation outcomes.
Body Layer: Data transformation and reporting.
"""

from __future__ import annotations

import time
from typing import Any

from .models import TestGenerationResult


# ID: 12bd31dc-af3b-4e6d-8063-768df4488dbf
class TestResultAggregator:
    """Turns raw test lists into structured Constitutional Evidence."""

    @staticmethod
    # ID: 4f6678df-d924-4d12-88c7-f76ba74cec51
    def build_final_result(
        file_path: str,
        attempts: list[dict],
        start_time: float,
        switches: int,
        patterns: dict,
    ) -> TestGenerationResult:
        """Constructs the high-level result object."""
        total = len(attempts)
        validated = sum(1 for a in attempts if a.get("validated"))
        sandbox_passed = sum(1 for a in attempts if a.get("sandbox_passed"))
        sandbox_failed = sum(
            1 for a in attempts if a.get("sandbox_ran") and not a.get("sandbox_passed")
        )
        skipped = sum(1 for a in attempts if a.get("skipped"))
        val_failures = sum(1 for a in attempts if a.get("validation_failure"))

        return TestGenerationResult(
            file_path=file_path,
            total_symbols=total,
            tests_generated=validated,
            tests_failed=sandbox_failed,
            tests_skipped=skipped,
            success_rate=validated / total if total > 0 else 0.0,
            strategy_switches=switches,
            patterns_learned=patterns,
            total_duration=time.time() - start_time,
            generated_tests=attempts,
            validation_failures=val_failures,
            sandbox_passed=sandbox_passed,
        )

    @staticmethod
    # ID: 7276dd03-4c7f-447d-978c-205faad6150d
    def format_summary_json(
        result: TestGenerationResult, session_dir: str, harness: Any
    ) -> dict:
        """Prepares the SUMMARY.json payload."""
        return {
            "file_path": result.file_path,
            "total_symbols": result.total_symbols,
            "stats": {
                "validated": result.tests_generated,
                "passed": result.sandbox_passed,
                "failed": result.tests_failed,
                "skipped": result.tests_skipped,
            },
            "validated_rate": f"{result.success_rate:.1%}",
            "artifacts_location": session_dir,
            "harness_detected": bool(harness.has_db_harness),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
