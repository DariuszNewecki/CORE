"""ADR-108 D4 — enforcement mappings follow the law root, not the code root.

The constitutional audit reads its policies from the IntentRepository and its
enforcement mappings from a separate loader. Those two halves are ONE corpus
and must share a root: the IntentRepository root. Rooting the enforcement
loader at ``repo_path`` (the code under audit) instead let the two diverge —
a BYOR consumer audited from CORE's source tree loaded every rule but mapped
none, collapsing the gate to a false-green PASS. This test pins the binding so
the regression cannot return silently.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mind.governance.audit_context import AuditorContext


def test_enforcement_loader_is_rooted_at_intent_repo_not_repo_path(
    tmp_path: Path,
) -> None:
    """enforcement_loader.intent_root == intent_repo.root, even when it differs
    from repo_path (the divergence the BYOR consumer hit)."""
    law_root = tmp_path / "law" / ".intent"
    law_root.mkdir(parents=True)
    code_root = tmp_path / "code"
    code_root.mkdir()

    intent_repo = MagicMock()
    intent_repo.root = law_root
    # list_policies() iterated by _load_governance_resources; an empty corpus is
    # fine for this binding test (the guarded exception path returns {}).
    intent_repo.list_policies.return_value = []

    context = AuditorContext(
        repo_path=code_root,
        intent_repository=intent_repo,
        stateless=True,
    )

    assert context.enforcement_loader.intent_root == law_root
    # And explicitly NOT the code-under-audit root.
    assert context.enforcement_loader.intent_root != code_root / ".intent"


def test_reload_governance_keeps_enforcement_rooted_at_intent_repo(
    tmp_path: Path,
) -> None:
    """reload_governance() must re-root the enforcement loader the same way."""
    law_root = tmp_path / "law" / ".intent"
    law_root.mkdir(parents=True)
    code_root = tmp_path / "code"
    code_root.mkdir()

    intent_repo = MagicMock()
    intent_repo.root = law_root
    intent_repo.list_policies.return_value = []

    context = AuditorContext(
        repo_path=code_root,
        intent_repository=intent_repo,
        stateless=True,
    )
    context.reload_governance()

    assert context.enforcement_loader.intent_root == law_root
