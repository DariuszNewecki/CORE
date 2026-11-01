# src/will/tools/policy_vectorizer.py
"""Policy vectorizer — PolicyVectorizer re-exported from shared.tools per ADR-063.

The core_policies collection is filled by the governed sync action
(body/atomic/sync_actions); will-layer callers import PolicyVectorizer from
here to search it.
"""

from __future__ import annotations

from shared.tools.policy_vectorizer import PolicyVectorizer


__all__ = ["PolicyVectorizer"]
