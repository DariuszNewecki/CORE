# src/features/autonomy/__init__.py
# ID: features.autonomy.init

"""
Autonomous Development Features

Exports both V1 (legacy) and V2 (constitutional) interfaces.
"""

from __future__ import annotations

# V1 Legacy interface (wraps V2)
from features.autonomy.autonomous_developer import develop_from_goal

# V2 Constitutional interface (recommended)
from features.autonomy.autonomous_developer_v2 import (
    develop_from_goal_v2,
    infer_workflow_type,
)


__all__ = [
    # Legacy interface (auto-infers workflow)
    "develop_from_goal",
    # V2 interface (explicit workflow types)
    "develop_from_goal_v2",
    "infer_workflow_type",
]
