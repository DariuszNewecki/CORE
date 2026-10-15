"""`no_swallowed_exceptions`: the AST check behind starter.no_bare_except (#1026).

The rule says: no bare ``except:``, no ``except Exception: pass``. Its regex
mapping only matched ``except:\\s*pass``, so a bare ``except:`` with a body
passed the starter pack's only blocking rule (found on the 'Prove it' run).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest
import yaml

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


def _check(src: str) -> list[str]:
    return PurityChecks.check_no_swallowed_exceptions(ast.parse(textwrap.dedent(src)))


@pytest.mark.parametrize(
    "src",
    [
        "try:\n    x()\nexcept:\n    print('bad row')\n",  # the proof-run case
        "try:\n    x()\nexcept:\n    pass\n",
        "try:\n    x()\nexcept Exception:\n    pass\n",
        "try:\n    x()\nexcept BaseException as exc:\n    ...\n",
    ],
)
# ID: 61660811-39aa-409d-a67c-944a4c86d39c
def test_swallowing_handlers_are_violations(src: str) -> None:
    assert len(_check(src)) == 1


@pytest.mark.parametrize(
    "src",
    [
        "try:\n    x()\nexcept (KeyError, ValueError):\n    log.warning('skip')\n",
        "try:\n    x()\nexcept Exception:\n    log.exception('failed')\n    raise\n",
        "try:\n    x()\nexcept ValueError:\n    pass\n",  # named, narrow
        "msg = 'never write a bare except: pass'\n",  # text, not code
    ],
)
# ID: 5a32b037-9fe1-4b9e-82cc-870d9c53307b
def test_named_or_handled_exceptions_pass(src: str) -> None:
    assert _check(src) == []


# ID: bccd682e-1c1b-4624-b999-359c27f333f1
def test_the_starter_and_hygiene_packs_use_the_ast_check() -> None:
    root = Path(__file__).resolve().parents[6]
    for rel in (
        "packs/starter_python.yaml",
        "packs/python_hygiene.yaml",
        "src/shared/_packs/starter_python.yaml",
        "src/shared/_packs/python_hygiene.yaml",
    ):
        mapping = yaml.safe_load((root / rel).read_text())["enforcement_mappings"][
            "starter.no_bare_except"
        ]
        assert mapping["engine"] == "ast_gate", rel
        assert mapping["params"]["check_type"] == "no_swallowed_exceptions", rel
