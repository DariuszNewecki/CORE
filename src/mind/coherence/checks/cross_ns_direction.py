# src/mind/coherence/checks/cross_ns_direction.py
"""CROSS_NS_DIRECTION — framework artifact referencing a project-namespace artifact.

Per ADR-144 D4 / topology §3.4 row 14.

Reads .intent/governance/namespace_manifest.yaml to build the project-classified
path set, then scans every framework-classified .specs/ artifact for text
references to any project-classified path.

A framework artifact that embeds a path reference to a project::core (or any
project::*) artifact violates the BYOR separability invariant: the framework
must be project-agnostic to be shipped unchanged to any governed deployment.

Scope: explicit .specs/ or .intent/ path-string references only. ADR-ID-only
references are out of scope in v1 (ADR-144 D4 rationale).

No LLM. No vectors. Structural grep against the namespace manifest.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .base import CheckSkipped, CoherenceCandidate


_PATH_REF = re.compile(r"\.(?:specs|intent)/[^\s\)\"\'\]>,]+")
_STATUS_ACCEPTED = re.compile(
    r"^\*\*Status:\*\*\s*Accepted", re.IGNORECASE | re.MULTILINE
)


# ID: 17b85354-49cc-4432-bc03-2d280de1ef0c
class CrossNsDirectionCheck:
    """Emit CROSS_NS_DIRECTION when a framework artifact references a project artifact.

    Raises CheckSkipped when the namespace manifest is absent (pre-migration
    state) so the orchestrator records 'skipped' rather than 'error'.
    """

    relation = "CROSS_NS_DIRECTION"

    # ID: f45a404f-8a3b-41bc-a5eb-af3e8acf7ff6
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root)

    # ID: 89ed0655-40e9-434a-a2c7-e34c3ce0c36e
    async def run(self) -> list[CoherenceCandidate]:
        manifest_path = (
            self._repo_root / ".intent" / "governance" / "namespace_manifest.yaml"
        )
        if not manifest_path.exists():
            raise CheckSkipped("namespace_manifest_absent")

        raw = manifest_path.read_text(encoding="utf-8", errors="replace")
        manifest = yaml.safe_load(raw)
        classifications = manifest.get("classifications", []) if manifest else []
        if not classifications:
            raise CheckSkipped("namespace_manifest_empty")

        framework_specs: list[str] = []
        project_paths: set[str] = set()

        for entry in classifications:
            path = entry.get("path", "")
            ns = entry.get("governance_namespace", "")
            if ns == "framework" and path.startswith(".specs/"):
                framework_specs.append(path)
            elif ns.startswith("project::"):
                project_paths.add(path)

        if not project_paths:
            return []

        candidates: list[CoherenceCandidate] = []

        for fw_rel in sorted(framework_specs):
            fw_path = self._repo_root / fw_rel
            try:
                content = fw_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            # Skip non-accepted ADRs — draft content may contain speculative
            # cross-references that do not represent committed dependencies.
            if fw_path.name.startswith("ADR-") and not _STATUS_ACCEPTED.search(content):
                continue

            refs = _extract_project_path_refs(content, project_paths)
            for ref in refs:
                candidates.append(
                    CoherenceCandidate(
                        relation=self.relation,
                        documents=[fw_rel, ref],
                        claim=(
                            f"Framework artifact '{fw_rel}' contains an explicit "
                            f"path reference to project-namespace artifact '{ref}'. "
                            "Framework artifacts must be project-agnostic for BYOR "
                            "separability."
                        ),
                        rationale=(
                            "Topology §3.4 row 14 (ADR-144 D2) forbids framework "
                            "artifacts from embedding references to project-classified "
                            "artifacts. A framework ADR or paper that names a specific "
                            "project path cannot be shipped unchanged to a BYOR "
                            "deployment — it encodes a dependency on a project that "
                            "may not exist. Either move the reference to a "
                            "project::core artifact, or reclassify the referenced "
                            "artifact as framework. See ADR-144 D4, ADR-075 D1/D6."
                        ),
                    )
                )
        return candidates


# ID: b2f9d387-c253-4de0-8902-6a2290afec67
def _extract_project_path_refs(content: str, project_paths: set[str]) -> list[str]:
    """Return sorted unique project-classified paths referenced in *content*.

    Strips trailing punctuation characters that may follow an embedded path
    in markdown prose (periods, commas, parentheses, quotes).
    """
    found: set[str] = set()
    for match in _PATH_REF.finditer(content):
        raw = match.group().rstrip(".,;)'\"` ")
        if raw in project_paths:
            found.add(raw)
    return sorted(found)
