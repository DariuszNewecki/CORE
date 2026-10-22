from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.coherence.checks.vocabulary import VocabularyCheck


# ID: e734bf27-6442-4c25-9f7e-f734ebd81717
def test_VocabularyCheck_run(tmp_path: Path) -> None:
    repo_root = tmp_path
    intent_root = repo_root / ".intent"
    meta_dir = intent_root / "META"
    meta_dir.mkdir(parents=True)
    vocab_data = {
        "terms": [
            {
                "canonical": "governance",
                "aliases": ["gov"],
            }
        ]
    }
    (meta_dir / "vocabulary.json").write_text(json.dumps(vocab_data), encoding="utf-8")

    artifact = repo_root / "docs" / "artifact.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("This mentions gov but not the other term.", encoding="utf-8")

    check = VocabularyCheck(repo_root=repo_root)
    check.relation = MagicMock()

    with (
        patch(
            "mind.coherence.checks.vocabulary.intent_root_for",
            return_value=intent_root,
        ),
        patch(
            "mind.coherence.checks.vocabulary._expand_alias_map",
            return_value={"gov": "governance"},
        ),
        patch(
            "mind.coherence.checks.vocabulary._iter_governance_markdown",
            return_value=[artifact],
        ),
        patch(
            "mind.coherence.checks.vocabulary.law_relpath",
            return_value="docs/artifact.md",
        ),
        patch(
            "mind.coherence.checks.vocabulary._whole_word",
            side_effect=lambda content, term: term in content,
        ),
    ):
        import asyncio

        candidates = asyncio.run(check.run())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.documents == ["docs/artifact.md"]
    assert "gov" in candidate.claim
    assert "governance" in candidate.claim


import asyncio


# ID: 8026e534-ef00-498c-98cf-73a1660c8474
def test_VocabularyCheck(tmp_path: Path) -> None:
    intent_root = tmp_path / ".intent"
    meta_dir = intent_root / "META"
    meta_dir.mkdir(parents=True)

    vocab_path = meta_dir / "vocabulary.json"
    vocab_path.write_text(
        json.dumps({"terms": [{"canonical": "governor", "aliases": ["gov"]}]}),
        encoding="utf-8",
    )

    artifact = tmp_path / "docs" / "governance.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("the gov approves", encoding="utf-8")

    check = VocabularyCheck(tmp_path)

    with (
        patch(
            "mind.coherence.checks.vocabulary.intent_root_for",
            return_value=intent_root,
        ),
        patch(
            "mind.coherence.checks.vocabulary._iter_governance_markdown",
            return_value=[artifact],
        ),
        patch(
            "mind.coherence.checks.vocabulary.law_relpath",
            return_value="docs/governance.md",
        ),
        patch(
            "mind.coherence.checks.vocabulary._expand_alias_map",
            return_value={"gov": "governor"},
        ),
    ):
        result = asyncio.run(check.run())

    assert len(result) == 1
    candidate = result[0]
    assert candidate.relation == "VOCABULARY"
    assert candidate.documents == ["docs/governance.md"]
    assert "gov" in candidate.claim
    assert "governor" in candidate.claim
