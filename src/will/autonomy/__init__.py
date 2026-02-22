# src/will/autonomy/__init__.py
# ID: 17f82677-e877-448d-b457-370b77bd2b31

"""
Autonomous Development Features
UPDATED: Moved to will.autonomy (Wave 1).
"""

from __future__ import annotations

# UPDATED: Direct internal import
from will.autonomy.autonomous_developer import (
    develop_from_goal,
    infer_workflow_type,
)


__all__ = [
    "develop_from_goal",
    "infer_workflow_type",
]
