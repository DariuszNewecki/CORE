"""Law-custody tests run as if the host had no durable custody ledger, unless a
test opts in: a developer host may have /opt/core/custody, CI does not."""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.law_custody.ledger import CUSTODY_LEDGER_ENV


@pytest.fixture(autouse=True)
def _no_durable_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        CUSTODY_LEDGER_ENV, str(tmp_path / "no-custody" / "ledger.jsonl")
    )
