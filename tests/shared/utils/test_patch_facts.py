# tests/shared/utils/test_patch_facts.py
"""patch_facts: what a patch does, and whether its retirement claims hold
(step 0, ADR-168 Amendment 2026-10-10; build plan U3)."""

from __future__ import annotations

from shared.utils.patch_facts import added_symbol_source, read_patch, verify_retires


_PATCH = (
    "diff --git a/src/a.py b/src/a.py\n"
    "--- a/src/a.py\n"
    "+++ b/src/a.py\n"
    "@@ -1,6 +1,6 @@\n"
    "-def old_helper():\n"
    "-    return 1\n"
    "-def keep(x):\n"
    "+def keep(x, y):\n"
    "     pass\n"
    "+class Fresh:\n"
    "+    def method(self):\n"
    "+        pass\n"
    "+def _private():\n"
    "+    pass\n"
    "diff --git a/src/gone.py b/src/gone.py\n"
    "deleted file mode 100644\n"
    "--- a/src/gone.py\n"
    "+++ /dev/null\n"
    "@@ -1 +0,0 @@\n"
    "-class Gone:\n"
    "diff --git a/src/new.py b/src/new.py\n"
    "new file mode 100644\n"
    "--- /dev/null\n"
    "+++ b/src/new.py\n"
    "@@ -0,0 +1 @@\n"
    "+async def fetch():\n"
    "diff --git a/README.md b/README.md\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1 +1 @@\n"
    "-def not_python():\n"
    "+text\n"
)


# ID: f59ed838-ee33-4b70-bd30-586f21fc606f
def test_files_are_classified_added_modified_deleted() -> None:
    facts = read_patch(_PATCH)
    assert facts.added == ["src/new.py"]
    assert facts.modified == ["src/a.py", "README.md"]
    assert facts.deleted == ["src/gone.py"]


# ID: 8d2d8150-a22b-46a6-8086-7578634ffb57
def test_symbols_removed_and_introduced_at_top_level_only() -> None:
    facts = read_patch(_PATCH)
    # keep() changed signature: removed and re-added, so neither retired nor new.
    assert facts.removed_symbols == {
        "src/a.py": ["old_helper"],
        "src/gone.py": ["Gone"],
    }
    # method() is not top-level; _private is not public; README is not Python.
    assert facts.new_public_symbols == {"src/a.py": ["Fresh"], "src/new.py": ["fetch"]}


# ID: 2842ce91-5465-44e5-9ccf-fc519dbfcb54
def test_retirement_claims_are_checked_against_the_patch() -> None:
    rows = verify_retires(
        ["src/gone.py", "src/a.py::old_helper", "src/a.py::keep", "src/a.py"],
        read_patch(_PATCH),
    )
    assert [r["verified"] for r in rows] == [True, True, False, False]
    assert "does not remove" in str(rows[2]["reason"])
    assert "does not delete" in str(rows[3]["reason"])


# ID: 7bfa29e5-5018-4ad2-8707-24299f135c56
def test_nothing_retired_is_an_empty_claim() -> None:
    assert verify_retires([], read_patch(_PATCH)) == []


# ID: 30ba5776-b57e-4383-8413-cab2036e4052
def test_added_symbol_source_is_the_symbol_block_only() -> None:
    assert added_symbol_source(_PATCH, "src/a.py", "Fresh") == (
        "class Fresh:\n    def method(self):\n        pass"
    )
    assert added_symbol_source(_PATCH, "src/new.py", "fetch") == "async def fetch():"
    assert added_symbol_source(_PATCH, "src/a.py", "old_helper") == ""
    assert added_symbol_source(_PATCH, "src/other.py", "Fresh") == ""
