# src/will/test_generation/models.py
# ID: will.test_generation.models
"""Shared data models for test generation — breaks circular import."""

from __future__ import annotations

from dataclasses import dataclass, field


# ID: tg-models-001
@dataclass
# ID: bb296ff4-c744-4924-885d-6658cf09510b
class TestGenerationResult:
    """High-level outcome of a test generation session."""

    file_path: str
    total_symbols: int
    tests_generated: int
    tests_failed: int
    tests_skipped: int
    success_rate: float
    strategy_switches: int
    patterns_learned: dict
    total_duration: float
    generated_tests: list[dict] = field(default_factory=list)
    validation_failures: int = 0
    sandbox_passed: int = 0
