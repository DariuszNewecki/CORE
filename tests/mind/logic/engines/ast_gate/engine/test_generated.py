from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.engine import ASTGateEngine


# ID: 7dd7b83e-6343-4fea-898e-e4b7c0256ced
def test_ASTGateEngine_verify(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.py"
    source_file.write_text("x = 1\n", encoding="utf-8")

    path_resolver = MagicMock()

    with (
        patch("mind.logic.engines.ast_gate.engine.CapabilityChecks"),
        patch("mind.logic.engines.ast_gate.engine.ModularityChecker"),
        patch("mind.logic.engines.ast_gate.engine.PurityChecks") as mock_purity,
    ):
        mock_purity.check_future_annotations.return_value = []
        engine = ASTGateEngine(path_resolver)

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            engine.verify(source_file, {"check_type": "future_annotations"})
        )

    assert result.ok is True
    assert result.violations == []
