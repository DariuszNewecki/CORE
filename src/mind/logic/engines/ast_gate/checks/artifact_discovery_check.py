# src/mind/logic/engines/ast_gate/checks/artifact_discovery_check.py

"""
ArtifactDiscoveryCheck — closes ADR-090 §Verification gate 9 (issue #566).

Detects files in artifact-pipeline directories that perform discovery via
hardcoded extension-based globs (Path.glob("*.ext"), Path.rglob("**/*.yaml"))
without consulting the IntentRepository artifact_type registry. The rule
formally commits to registry routing
(architecture.artifact_discovery_through_registry); this check makes the
commitment self-enforcing.

Gate sequence (any failed gate short-circuits the file to no-violation):

1. Location — file path must live under one of the artifact-pipeline
   prefixes (will/workers, mind/governance, mind/coherence,
   body/services/crawl_service). Files outside these are out of scope
   per the rule's "non-discovery file walks are out of scope" carve-out.

2. Carve-outs — gateway code, test files, and the IntentRepository file
   itself are always exempt.

3. Bypass detection — if the file imports get_intent_repository OR calls
   IntentRepository.list_artifact_types() / .get_artifact_type(), the
   file is presumed to be consulting the registry and any globs are
   legitimate (registry result feeds the glob pattern).

Only files passing all three gates are inspected for the offending
glob/rglob call shape.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import ClassVar


# ID: 3cf25eee-a8a6-42f0-ac0a-c0554f6afe46
class ArtifactDiscoveryCheck:
    """Detect hardcoded-extension discovery globs that bypass the
    IntentRepository artifact_type registry (#566 / ADR-090 gate 9)."""

    # Artifact-pipeline directories per the issue body. A file outside
    # these is out of scope (non-discovery file walks — test runners,
    # config loaders, build tooling — are explicitly carved out by the
    # rule statement).
    _PIPELINE_PREFIXES: ClassVar[tuple[str, ...]] = (
        "src/will/workers/",
        "src/mind/governance/",
        "src/mind/coherence/",
        "src/body/services/crawl_service/",
    )

    # Always-skip paths regardless of whether the suspect call appears.
    _CARVEOUT_PREFIXES: ClassVar[tuple[str, ...]] = (
        "src/shared/infrastructure/intent/",  # the gateway itself
        "tests/",
    )

    # File names whose own job is to BE the registry — exempt by identity,
    # not by directory. intent_repository.py lives in the gateway already
    # (covered by the gateway carve-out) but listed defensively in case of
    # future relocation.
    _CARVEOUT_FILENAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "intent_repository.py",
        }
    )

    # The glob/rglob method attribute names that perform filesystem
    # discovery. Both pathlib.Path.glob and Path.rglob match this pattern.
    _GLOB_METHODS: ClassVar[frozenset[str]] = frozenset({"glob", "rglob"})

    # Detection: any registry API the file might import or call. Presence
    # of any of these names in the file's AST is treated as registry
    # consultation, exempting the file from the check.
    _REGISTRY_API_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "get_intent_repository",
            "list_artifact_types",
            "get_artifact_type",
        }
    )

    # A "hardcoded extension pattern" is a string literal containing
    # *.<ext> where ext is at least one alphanumeric char. Catches
    # "*.py", "**/*.yaml", "src/**/*.json", etc. Does NOT match
    # bare names like "README" or substring matches like "test_*".
    _EXTENSION_GLOB_RE: ClassVar[re.Pattern[str]] = re.compile(r"\*\.[A-Za-z0-9]+")

    @classmethod
    # ID: 04c01e17-17c3-42e7-b47a-fe128b63ccad
    def check_artifact_discovery_through_registry(
        cls,
        tree: ast.AST,
        file_path: Path,
    ) -> list[str]:
        """Gate 9 of ADR-090: detect rglob/glob bypass of the artifact_type registry.

        Returns one violation per suspect glob/rglob call in scope; empty
        list when any gate (location, carve-out, registry-bypass) fails.
        """
        normalized = str(file_path).replace("\\", "/")

        # Gate 2 (carve-outs first — cheapest to evaluate)
        if any(carve in normalized for carve in cls._CARVEOUT_PREFIXES):
            return []
        if Path(normalized).name in cls._CARVEOUT_FILENAMES:
            return []

        # Gate 1 (location)
        if not any(prefix in normalized for prefix in cls._PIPELINE_PREFIXES):
            return []

        # Gate 3 (registry-consultation bypass)
        if cls._file_consults_registry(tree):
            return []

        # Inspect every Call node for the suspect shape.
        findings: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                violation = cls._inspect_call(node)
                if violation:
                    findings.append(violation)

        return findings

    @classmethod
    def _file_consults_registry(cls, tree: ast.AST) -> bool:
        """True if any of the registry API names appear in the file's AST.

        Walks every Name and Attribute node in the tree. This errs on the
        side of false-negative for the bypass check (file is exempted if
        even a single reference to a registry API exists), matching the
        rule's spirit: a file that knows the registry exists is presumed
        to be using it.
        """
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in cls._REGISTRY_API_NAMES:
                return True
            if isinstance(node, ast.Attribute) and node.attr in cls._REGISTRY_API_NAMES:
                return True
        return False

    @classmethod
    def _inspect_call(cls, node: ast.Call) -> str | None:
        """Return a violation message if node is a suspect glob/rglob call.

        Match shape: <expr>.glob("*.ext") / <expr>.rglob("**/*.ext").
        - The method name must be in _GLOB_METHODS.
        - The first positional arg must be a string Constant.
        - The string must contain a hardcoded *.<ext> pattern.

        Non-Constant args (variables, f-strings with substituted extensions)
        are intentionally not flagged — they may be parameterised legitimately.
        """
        if not isinstance(node.func, ast.Attribute):
            return None
        method_name = node.func.attr
        if method_name not in cls._GLOB_METHODS:
            return None
        if not node.args:
            return None
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            return None
        pattern = first.value
        if not cls._EXTENSION_GLOB_RE.search(pattern):
            return None

        line = getattr(node, "lineno", "?")
        return (
            f"Line {line}: artifact-pipeline file performs discovery via "
            f"{method_name}({pattern!r}) without consulting the "
            f"IntentRepository artifact_type registry (ADR-090 gate 9). "
            f"Route discovery through IntentRepository.list_artifact_types() "
            f"or .get_artifact_type(id) so registry edits propagate without "
            f"per-file maintenance."
        )
