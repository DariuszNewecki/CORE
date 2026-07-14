# tests/shared/utils/test_test_gen_utils__strip_leading_future_imports.py

"""strip_leading_future_imports — #792 append-path SyntaxError guard.

Source: shared.utils.test_gen_utils.strip_leading_future_imports

The context_aware_test_gen prompt mandates every generated snippet begin with
`from __future__ import annotations`. build.test_for_symbol appends snippets to
an existing test file; the mandated import then lands mid-file and raises
`SyntaxError: from __future__ imports must occur at the beginning of the file`
at pytest collection (#792). This helper strips the snippet's own copy so the
caller controls the single top-of-file future import.
"""

from __future__ import annotations

import ast

from shared.utils.test_gen_utils import strip_leading_future_imports


def test_strips_leading_future_import():
    code = "from __future__ import annotations\n\n\ndef test_x():\n    assert True\n"
    result = strip_leading_future_imports(code)
    assert "from __future__" not in result
    assert result.startswith("def test_x():")


def test_preserves_body_without_future_import():
    code = "def test_x():\n    assert True\n"
    assert strip_leading_future_imports(code) == "def test_x():\n    assert True"


def test_strips_multiple_future_imports():
    code = (
        "from __future__ import annotations\n"
        "from __future__ import division\n\n"
        "import pytest\n\n\ndef test_x():\n    assert True\n"
    )
    result = strip_leading_future_imports(code)
    assert "from __future__" not in result
    assert result.startswith("import pytest")


def test_preserves_leading_comment_but_drops_future_import():
    code = "# a leading comment\nfrom __future__ import annotations\n\nx = 1\n"
    result = strip_leading_future_imports(code)
    assert "from __future__" not in result
    assert result.startswith("# a leading comment")
    assert "x = 1" in result


def test_leaves_future_import_after_real_code_untouched():
    # A `from __future__` after real code is already a caller bug — the helper
    # only cleans the leading header region, it does not rewrite the whole file.
    code = "x = 1\nfrom __future__ import annotations\n"
    result = strip_leading_future_imports(code)
    assert result == "x = 1\nfrom __future__ import annotations"


def test_appended_result_parses_cleanly():
    # The actual #792 scenario: an existing file (with its own top future import)
    # plus a stripped snippet must parse without SyntaxError.
    existing = "from __future__ import annotations\n\n\ndef test_a():\n    assert True\n"
    snippet = "from __future__ import annotations\n\n\ndef test_b():\n    assert True\n"
    appended = (
        existing.rstrip() + "\n\n\n" + strip_leading_future_imports(snippet) + "\n"
    )
    # Would raise SyntaxError before the fix (mid-file future import).
    ast.parse(appended)
    assert appended.count("from __future__") == 1
