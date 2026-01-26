# src/features/test_generation/__init__.py

"""
Test Generation V2 - Component-based adaptive test generation.

This is the NEW test generation system that replaces AccumulativeTestService.

Key Features:
- File analysis before generation
- Strategy selection based on file type
- Failure pattern recognition
- Automatic strategy adaptation
- Learns from mistakes

Architecture:
- Uses Analyzers (FileAnalyzer, SymbolExtractor)
- Uses Evaluators (FailureEvaluator)
- Uses Strategists (TestStrategist)
- Composes into AdaptiveTestGenerator

Usage:
    from features.test_generation_v2 import AdaptiveTestGenerator
    from will.orchestration.cognitive_service import CognitiveService

    cognitive_service = CognitiveService()
    generator = AdaptiveTestGenerator(cognitive_service)

    result = await generator.generate_tests_for_file(
        file_path="src/models/knowledge.py",
        write=True
    )

    print(f"Success rate: {result.success_rate:.1%}")
    print(f"Strategy switches: {result.strategy_switches}")
"""

from __future__ import annotations

from .adaptive_test_generator import AdaptiveTestGenerator, TestGenerationResult


__all__ = [
    "AdaptiveTestGenerator",
    "TestGenerationResult",
]
