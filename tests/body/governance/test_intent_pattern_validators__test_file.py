"""Tests for PatternValidators.validate_test_file_pattern (issue #574).

Closes the hallucinated-imports gap in IntentGuard.validate_generated_code
for ``pattern_id="test_file"``. The validator enforces two rules declared
in ``.intent/rules/code/imports.json``:

- ``code.imports.generated_must_resolve`` — every absolute import statement
  must resolve to an existing module on the Python path.
- ``code.imports.generated_no_relative`` — relative imports
  (``from .foo import x``) are forbidden in generated code.

The validator looks up rule statements from IntentRepository, so the source
of truth for the violation message is ``.intent/`` — not the validator code.
"""

from __future__ import annotations

import pytest

from body.governance.intent_pattern_validators import PatternValidators


# ID: edb557bc-fb64-408b-aea6-0b03c95f945b
def test_hallucinated_module_produces_must_resolve_violation() -> None:
    """The concrete #574 repro: ``from shared.domain.engine import EngineResult``.

    ``shared.domain`` does not exist in the tree. The validator must flag it
    with ``code.imports.generated_must_resolve`` and name the unresolvable
    module in the violation message.
    """
    code = "from shared.domain.engine import EngineResult\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_must_resolve"
    assert "shared.domain.engine" in out[0].message


# ID: 28a16563-b284-4e92-bf2b-95a86fa08bdc
def test_valid_imports_produce_no_violations() -> None:
    """Real repo modules + stdlib + ``__future__`` all resolve cleanly."""
    code = (
        "from __future__ import annotations\n"
        "import pytest\n"
        "from shared.path_resolver import PathResolver\n"
    )
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert out == []


# ID: 7827ea29-1505-4727-8fc0-70ef16ae568e
def test_future_imports_always_skipped() -> None:
    """``from __future__ import …`` is always valid and never flagged, even
    though ``__future__`` is technically a stdlib module — the validator
    short-circuits on it explicitly.
    """
    code = "from __future__ import annotations\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert out == []


# ID: c351c94d-eeef-48ba-85cd-5d289ac3570c
def test_relative_import_is_no_relative_violation() -> None:
    """Relative imports (``level > 0``) are flagged with
    ``code.imports.generated_no_relative``.
    """
    code = "from .helpers import setup\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_no_relative"


# ID: f2b1311d-ceba-42e8-bb92-5163d463ca33
def test_double_dot_relative_import_is_no_relative_violation() -> None:
    """``from ..pkg import x`` (level=2) is reported the same way as level=1."""
    code = "from ..pkg import Thing\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_no_relative"


# ID: 01d080b1-f39f-42eb-a0a7-fc5c0e6e9840
def test_relative_import_skips_resolve_check() -> None:
    """A relative import gets the no_relative violation only — not also a
    must_resolve violation. ``from .foo import x`` has no absolute module
    name ``find_spec`` could meaningfully resolve.
    """
    code = "from .helpers import setup\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    rule_names = {v.rule_name for v in out}
    assert rule_names == {"code.imports.generated_no_relative"}


# ID: de7fc632-4b32-4410-9a76-17e4d35e8125
def test_mixed_valid_and_hallucinated_reports_only_hallucinated() -> None:
    """When some imports are good and one is hallucinated, the validator
    reports only the hallucinated one — no false positives on the valid imports.
    """
    code = (
        "import pytest\n"
        "from shared.path_resolver import PathResolver\n"
        "from shared.domain.engine import EngineResult\n"
    )
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_must_resolve"
    assert "shared.domain.engine" in out[0].message


# ID: 70282bac-0955-43b5-bb27-0d35519c8939
def test_multiple_hallucinated_modules_each_reported_separately() -> None:
    """Each hallucinated module produces its own violation — the validator
    walks every ImportFrom/Import node, not just the first failing one.
    """
    code = (
        "from shared.domain.engine import EngineResult\n"
        "from shared.fake.thing import Thing\n"
    )
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 2
    assert all(
        v.rule_name == "code.imports.generated_must_resolve" for v in out
    )


# ID: e9bf2c6e-1994-46c3-a241-e4a7c579d333
def test_plain_import_alias_form_resolves() -> None:
    """``import x.y.z`` is walked via ast.Import / Import.names, distinct from
    the ImportFrom path. A hallucinated dotted import must be flagged.
    """
    code = "import shared.domain.engine\n"
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_must_resolve"
    assert "shared.domain.engine" in out[0].message


# ID: 1c5036eb-8e2d-4ea4-a834-da6551bdea57
def test_syntax_error_returns_empty_list() -> None:
    """A SyntaxError in the input returns an empty list — the syntax check
    is handled upstream in IntentGuard.validate_generated_code step 2;
    re-emitting from this validator would duplicate the violation.
    """
    code = "from shared import (\n"  # unterminated paren
    out = PatternValidators.validate_test_file_pattern(
        code, "tests/test_generated.py"
    )
    assert out == []


# ID: 986d0ce6-e2c7-4be2-9e4c-1fafd08f66e3
def test_dispatch_via_validate_routes_to_test_file_validator() -> None:
    """``PatternValidators.validate(code, pattern_id="test_file", …)`` must
    dispatch into ``validate_test_file_pattern``, not fall through to the
    "no validator" empty-list branch.
    """
    code = "from shared.domain.engine import Thing\n"
    out = PatternValidators.validate(
        code,
        pattern_id="test_file",
        component_type="test",
        target_path="tests/test_generated.py",
    )
    assert len(out) == 1
    assert out[0].rule_name == "code.imports.generated_must_resolve"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
