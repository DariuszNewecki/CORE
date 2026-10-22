from __future__ import annotations

from unittest.mock import call, patch

from mind.enforcement.audit import lint


# ID: 77a91783-0201-4d55-93c8-96194752eb72
def test_lint():
    with patch("mind.enforcement.audit.run_poetry_command") as mock_run:
        lint()

    assert mock_run.call_args_list == [
        call(
            "🔎 Checking code format with Black...",
            ["black", "--check", "src", "tests"],
        ),
        call(
            "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
        ),
    ]
