# tests/will/remediation/crate_canary/test_ceremony_tools.py
"""The remediation ceremony runs the interpreter's own black and ruff.

2026-10-12: under the release runtime every ceremony step failed with
"No such file or directory: 'poetry'" -- a release venv has no Poetry.
"""

from __future__ import annotations

import inspect

from will.remediation import crate_canary


# ID: cbc3da17-08e0-429b-8c2c-6c319969280e
def test_ceremony_does_not_shell_out_through_poetry() -> None:
    assert '"poetry"' not in inspect.getsource(crate_canary)
