"""Regression tests for governance.dangerous_execution_primitives (#810).

os.environ / os.getenv were removed from the rule's forbidden-primitives
list: a config read executes nothing, so it was never the risk the rule is
named for. These tests load the real
.intent/enforcement/mappings/architecture/governance_basics.yaml mapping
(the actual config the audit engine consumes) and exercise the real
PurityChecks.check_forbidden_primitives function against it, so this proves
the live audit behavior, not just the YAML's literal content.
"""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


_REPO_ROOT = Path(__file__).resolve().parents[6]
_MAPPING_PATH = (
    _REPO_ROOT
    / ".intent"
    / "enforcement"
    / "mappings"
    / "architecture"
    / "governance_basics.yaml"
)


def _forbidden_list() -> list[str]:
    with _MAPPING_PATH.open() as fh:
        doc = yaml.safe_load(fh)
    return doc["mappings"]["governance.dangerous_execution_primitives"]["params"][
        "forbidden"
    ]


def test_forbidden_list_no_longer_contains_env_reads() -> None:
    forbidden = _forbidden_list()
    assert "os.environ" not in forbidden
    assert "os.getenv" not in forbidden


def test_forbidden_list_still_contains_genuine_execution_primitives() -> None:
    forbidden = _forbidden_list()
    for primitive in (
        "eval",
        "exec",
        "compile",
        "os.system",
        "subprocess.Popen",
        "subprocess.call",
        "subprocess.run",
        "Popen",
    ):
        assert primitive in forbidden, f"{primitive} must remain forbidden"


def test_ordinary_env_reads_no_longer_flagged() -> None:
    """The #810 reproduction case: os.environ.get(...) / os.getenv(...)."""
    forbidden = _forbidden_list()
    source = (
        "import os\n"
        "base_url = os.environ.get('CORE_API_URL')\n"
        "path = os.getenv('PATH')\n"
    )
    tree = ast.parse(source)
    violations = PurityChecks.check_forbidden_primitives(tree, forbidden)
    assert violations == []


def test_genuine_execution_primitives_still_flagged() -> None:
    forbidden = _forbidden_list()
    cases = {
        "eval('1 + 1')": "eval",
        "exec('pass')": "exec",
        "compile('pass', '<string>', 'exec')": "compile",
        "os.system('ls')": "os.system",
        "subprocess.Popen(['ls'])": "subprocess.Popen",
        "subprocess.run(['ls'])": "subprocess.run",
    }
    for snippet, expected_primitive in cases.items():
        source = f"import os, subprocess\n{snippet}\n"
        tree = ast.parse(source)
        violations = PurityChecks.check_forbidden_primitives(tree, forbidden)
        assert violations, f"expected a violation for {snippet!r}"
        assert any(expected_primitive in v for v in violations), (
            f"expected {expected_primitive!r} named in violations for "
            f"{snippet!r}, got {violations!r}"
        )


def test_bare_import_execution_primitive_still_flagged() -> None:
    """Bare-import form (`from os import system`) resolves through the
    alias map -- unaffected by the env-read removal, still caught."""
    forbidden = _forbidden_list()
    source = "from os import system\nsystem('ls')\n"
    tree = ast.parse(source)
    violations = PurityChecks.check_forbidden_primitives(tree, forbidden)
    assert violations
