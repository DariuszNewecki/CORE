# src/will/remediation/models.py
"""
Shared dataclasses for the RemediationCeremony package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _RemediationPlan:
    """
    Output of the RUNTIME planning phase.

    This is evidence assembled before the execution ceremony begins.
    It is passed to the LLM as architectural context — not as authority.
    The LLM must treat it as advisory input, not as a directive.
    """

    file_path: str
    original_source: str
    baseline_sha: str
    violations_summary: str
    # architectural_context carries the deterministic brief as evidence.
    # It is NOT a planning authority. It is evidence of the file's
    # detected role, responsibility clusters, and candidate strategies.
    # The LLM is free to disagree with it; it must satisfy the rule.
    architectural_context: dict[str, Any]
    context_text: str
