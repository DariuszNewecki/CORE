# tests/shared/models/test_generation_mode.py
"""Tests for GenerationMode StrEnum (ADR-135 D1)."""

from __future__ import annotations

from shared.models.generation_mode import GenerationMode


def test_values_are_correct_strings():
    assert GenerationMode.SINGLE_SHOT == "single_shot"
    assert GenerationMode.ITERATIVE == "iterative"


def test_str_comparison():
    assert GenerationMode.ITERATIVE == "iterative"
    assert GenerationMode.SINGLE_SHOT == "single_shot"


def test_exportable_from_shared_models():
    from shared.models import GenerationMode as GM

    assert GM.ITERATIVE == "iterative"


def test_closed_vocabulary():
    members = {m.value for m in GenerationMode}
    assert members == {"single_shot", "iterative"}
