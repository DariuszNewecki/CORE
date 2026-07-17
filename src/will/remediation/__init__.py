# src/will/remediation/__init__.py
"""
RemediationCeremony package.

ADR-153. The LLM/Crate/Canary/commit ceremony extracted from
ViolationRemediator (will/workers/violation_remediator_body/) so that
ViolationExecutorWorker and CLI file-mode no longer need to import and
instantiate a Worker subclass to run it.
"""

from .blackboard import (
    NullRemediationBlackboard,
    RemediationBlackboard,
    WorkerRemediationBlackboard,
)
from .ceremony import RemediationCeremony


__all__ = [
    "NullRemediationBlackboard",
    "RemediationBlackboard",
    "RemediationCeremony",
    "WorkerRemediationBlackboard",
]
