"""Tests for ArtifactDiscoveryCheck (#566 / ADR-090 gate 9).

The check fires when a file in an artifact-pipeline directory performs
discovery via a hardcoded extension-based glob without consulting the
IntentRepository artifact_type registry. Three gates (location,
carve-out, registry-bypass) keep precision tight; these tests exercise
each gate plus the suspect-call detection itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.checks.artifact_discovery_check import (
    ArtifactDiscoveryCheck,
)


def _check(code: str, path: str) -> list[str]:
    """Parse code, run the check against the synthetic path."""
    tree = ast.parse(code)
    return ArtifactDiscoveryCheck.check_artifact_discovery_through_registry(
        tree, Path(path)
    )


# ID: 605d6b18-9037-40df-9c65-b15d3f98ac3e
def test_pipeline_file_with_rglob_extension_pattern_flags() -> None:
    """File in an artifact-pipeline directory using rglob('*.ext') without
    registry consultation produces one violation per call. This is the
    #566 shape — the rule's central enforcement target.
    """
    code = (
        "from pathlib import Path\n"
        "def discover():\n"
        "    return list(Path('.').rglob('*.yaml'))\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert len(findings) == 1
    assert "rglob" in findings[0]
    assert "'*.yaml'" in findings[0]
    assert "ADR-090 gate 9" in findings[0]


# ID: 3b1edc1b-807d-4a5d-882f-0873456b7231
def test_pipeline_file_with_registry_import_is_exempt() -> None:
    """Even with a hardcoded glob, presence of a registry-API name in the
    file's AST exempts the file — the rule's spirit is that files
    consulting the registry are presumed legitimate.
    """
    code = (
        "from pathlib import Path\n"
        "from shared.infrastructure.intent.intent_repository "
        "import get_intent_repository\n"
        "def discover():\n"
        "    repo = get_intent_repository()\n"
        "    return list(Path('.').rglob('*.yaml'))\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert findings == []


# ID: e2f6733e-8c54-42b8-abc4-ce55f019cae6
def test_pipeline_file_with_list_artifact_types_call_is_exempt() -> None:
    """A direct call to IntentRepository.list_artifact_types() also exempts
    — the bypass-detection walks Name AND Attribute nodes.
    """
    code = (
        "from pathlib import Path\n"
        "def discover(repo):\n"
        "    types = repo.list_artifact_types()\n"
        "    return list(Path('.').rglob('*.yaml'))\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert findings == []


# ID: 76d89b61-51ab-48fc-854a-280700279760
def test_test_file_path_is_exempt() -> None:
    """The rule statement explicitly carves out test runners. A test file
    using the same glob shape produces no violation regardless of the
    code it contains.
    """
    code = "from pathlib import Path\ndef t(): Path('.').rglob('*.py')\n"
    findings = _check(code, "tests/mind/test_something.py")
    assert findings == []


# ID: ee8cb911-e6b5-46ab-81d2-297fb30999f4
def test_gateway_file_is_exempt() -> None:
    """src/shared/infrastructure/intent/ is the canonical gateway — it
    legitimately walks .intent/ and is excluded from this check.
    """
    code = "from pathlib import Path\ndef walk(): Path('.').rglob('*.yaml')\n"
    findings = _check(code, "src/shared/infrastructure/intent/loader.py")
    assert findings == []


# ID: 9ef13456-d5df-411a-9d09-1847fc46fb66
def test_file_outside_pipeline_directories_is_exempt() -> None:
    """Non-discovery file walks (CLI tools, body services not in
    crawl_service) are out of scope per the rule statement. A
    src/cli/ file using rglob is not flagged.
    """
    code = "from pathlib import Path\ndef cmd(): Path('.').rglob('*.py')\n"
    findings = _check(code, "src/cli/commands/inspect.py")
    assert findings == []


# ID: 4e5d3557-8e8c-489e-9301-d0da56e271d5
def test_non_extension_glob_pattern_does_not_flag() -> None:
    """rglob('README'), glob('CHANGELOG') and similar non-extension
    patterns don't match the rule's "hardcoded extension-based" framing.
    Only patterns containing *.<ext> are flagged.
    """
    code = (
        "from pathlib import Path\n"
        "def find_readmes():\n"
        "    return list(Path('.').rglob('README'))\n"
        "def find_changelogs():\n"
        "    return list(Path('.').glob('CHANGELOG'))\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert findings == []


# ID: 708d6450-f638-4276-bd4e-07eed90faeac
def test_variable_argument_is_not_flagged() -> None:
    """When the glob argument is a variable (not a string Constant), the
    pattern may be supplied legitimately from elsewhere — the check
    intentionally does not flag this case to avoid false positives on
    parameterised callers.
    """
    code = (
        "from pathlib import Path\n"
        "def discover(pattern):\n"
        "    return list(Path('.').rglob(pattern))\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert findings == []


def test_substring_extension_pattern_flags() -> None:
    """Patterns like 'ADR-*.md' contain a *.ext substring and ARE flagged.
    Matches the spirit of the rule — extension-based discovery in any form.
    """
    code = (
        "from pathlib import Path\n"
        "def find_adrs():\n"
        "    return list(Path('.').glob('ADR-*.md'))\n"
    )
    findings = _check(code, "src/mind/coherence/checks/some_check.py")
    assert len(findings) == 1
    assert "ADR-*.md" in findings[0]


def test_multiple_suspect_calls_each_flagged() -> None:
    """Each suspect glob call produces its own violation — no dedup at
    file level — so the operator sees every call site.
    """
    code = (
        "from pathlib import Path\n"
        "def a(): Path('.').rglob('*.yaml')\n"
        "def b(): Path('.').rglob('*.json')\n"
    )
    findings = _check(code, "src/mind/governance/some_discoverer.py")
    assert len(findings) == 2


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
