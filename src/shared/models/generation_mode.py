# src/shared/models/generation_mode.py
"""
GenerationMode — closed vocabulary for LLM generation execution strategies.

Two modes are defined (ADR-135 D1):
  single_shot — one generate call, one optional repair call (existing behaviour).
  iterative   — loop (generate → accept → feed violations back) up to governed cap.

Authority: .intent/enforcement/config/generation_budget.yaml governs the iteration
cap per task_type. This enum is the closed vocabulary both the action layer and
the flow manifests reference.
"""

from __future__ import annotations

from enum import StrEnum


# ID: 5ef8e0ba-13b7-4519-adc5-289e048dc542
class GenerationMode(StrEnum):
    """Execution strategy for a generation step (ADR-135 D1)."""

    SINGLE_SHOT = "single_shot"
    ITERATIVE = "iterative"
