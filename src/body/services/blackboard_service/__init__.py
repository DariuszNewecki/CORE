# src/body/services/blackboard_service/__init__.py
# blackboard_service/__init__.py
"""
Package split from blackboard_service.py.
"""

from __future__ import annotations

from .blackboard_proposal_service import BlackboardProposalService
from .blackboard_service import BlackboardService


# ID: 88382dd0-e47a-4538-88b7-40c050a649f8
class BlackboardService(BlackboardService, BlackboardProposalService):
    pass
