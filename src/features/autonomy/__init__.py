# src/features/autonomy/__init__.py
# ID: 0fe3a9ff-3ca1-428f-9147-7a96347f9c43

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
