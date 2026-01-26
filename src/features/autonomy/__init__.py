# src/features/autonomy/__init__.py
# ID: features.autonomy.init

"""
Autonomous Development Features

Exports both V1 (legacy) and V2 (constitutional) interfaces.
"""

from __future__ import annotations

# Constitutional interface (recommended)
from features.autonomy.autonomous_developer import (
    develop_from_goal,
    infer_workflow_type,
)


__all__ = [
    # V2 interface (explicit workflow types)
    "develop_from_goal",
    "infer_workflow_type",
]
