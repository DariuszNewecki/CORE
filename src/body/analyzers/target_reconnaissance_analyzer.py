# src/body/analyzers/target_reconnaissance_analyzer.py

"""Target Reconnaissance Analyzer — PARSE-phase comprehension of an unfamiliar target.

Produces a deterministic, read-only account of what a bound target repository
actually contains, so that planning is grounded in the target rather than in
assumptions carried over from CORE's own shape (#895 U1, ADR-159 apparatus
design section 6).

Classification routes entirely through the artifact_type registry: every file is
matched against the discovery globs each registered type declares. Nothing in
this module names a governed directory, an extension, or a layout by string
literal, so the report stays correct for targets that look nothing like CORE --
and an absence is reported as an absence rather than silently read as zero.

CONSTITUTIONAL:
- PARSE phase: pure read, no mutations, no side effects.
- Deterministic: sorted traversal, no timestamps or absolute paths in the report.
- Discovery consults IntentRepository.list_artifact_types() -- no hardcoded globs
  (architecture.artifact_discovery_through_registry).
- Receives its target via execute() kwargs -- no Settings dependency.
"""

from __future__ import annotations

import fnmatch
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from shared.component_primitive import ComponentResult
from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    get_intent_repository,
)
from shared.logger import getLogger
from shared.models.refusal_result import RefusalResult


logger = getLogger(__name__)

# Derived artifacts, not target content. A tool cache can outnumber the target's
# own files several times over and would otherwise dominate every count here.
_SKIP_DIR_PARTS: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        "build",
        "dist",
        "__pycache__",
        "node_modules",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
    }
)

# Directory listing depth. Deep trees are summarised by count rather than
# enumerated, so the report stays a fixed size regardless of target size.
_LAYOUT_DEPTH: int = 2


@dataclass(frozen=True)
# ID: 6bd13308-3c45-4ef8-910e-6972000678d1
class UnavailableTopic:
    """A reconnaissance topic that could not be observed, and why.

    An explicit absence is a finding. Recording it separately from an empty
    result keeps 'the target has no tests' distinguishable from 'tests were
    never looked for', which is the distinction a planner needs and the one a
    bare zero destroys.
    """

    topic: str
    reason: str

    # ID: 5edad181-a689-4ac8-b69d-36ba72e33ff1
    def as_dict(self) -> dict[str, str]:
        """Return the topic as a plain dict for blackboard payloads."""
        return {"topic": self.topic, "reason": self.reason}


# ID: 4ea32346-464c-4478-95f6-36786f02a565
class TargetReconnaissanceAnalyzer(BaseAnalyzer):
    """Extract a deterministic structural account of a bound target repository.

    Returns ComponentResult with data keys:
    - recon_text: formatted report string, fed to PlannerAgent as its
      reconnaissance_report argument
    - recon_raw: structured dict of the same facts, for the blackboard record
    - unavailable: list of {topic, reason} dicts -- observed absences
    - recon_digest: full 64-hex SHA-256 over recon_text, for evidence pinning
    """

    component_id: str = "target_reconnaissance_analyzer"

    def __init__(self, intent_repository: IntentRepository | None = None) -> None:
        self._repository = intent_repository

    # ID: 8eefd004-b72e-43b1-90aa-b14dc75e2bf9
    async def execute(self, repo_path: Path | str, **kwargs: Any) -> ComponentResult:
        """Walk repo_path and describe what the target actually contains.

        Args:
            repo_path: Root path of the bound target to reconnoitre.

        Returns:
            ComponentResult with ok=True and the recon report in data, or a
            RefusalResult when the target path is not a readable directory --
            an unusable target is a refusal, not a technical error.
        """
        start = time.monotonic()
        target = Path(repo_path).resolve()

        if not target.is_dir():
            return RefusalResult.boundary_violation(
                component_id=self.component_id,
                phase=self.phase,
                reason=(
                    "Reconnaissance requires a readable target directory; "
                    f"{target} is not one."
                ),
                boundary="bound target root",
                original_request=str(repo_path),
            )

        unavailable: list[UnavailableTopic] = []

        files = self._collect_files(target)
        if not files:
            unavailable.append(
                UnavailableTopic(
                    topic="contents",
                    reason="target contains no readable files outside skipped directories",
                )
            )

        type_globs, registry_note = self._load_type_globs()
        if registry_note is not None:
            unavailable.append(registry_note)

        classified, unclassified = self._classify(files, type_globs)

        for type_id, globs in sorted(type_globs.items()):
            if not globs:
                unavailable.append(
                    UnavailableTopic(
                        topic=f"artifact_type:{type_id}",
                        reason="registered type declares no discovery globs; "
                        "presence cannot be determined by discovery alone",
                    )
                )
            elif type_id not in classified:
                unavailable.append(
                    UnavailableTopic(
                        topic=f"artifact_type:{type_id}",
                        reason="no file in the target matches this type's discovery globs",
                    )
                )

        raw: dict[str, Any] = {
            "file_count": len(files),
            "layout": self._layout(target, files),
            "artifact_types_present": {
                k: len(v) for k, v in sorted(classified.items())
            },
            "artifact_type_examples": {
                k: sorted(v)[:3] for k, v in sorted(classified.items())
            },
            "unclassified_count": len(unclassified),
            "unclassified_suffixes": self._suffix_histogram(unclassified),
        }

        text = self._render(raw, unavailable)
        # Full digest, not a prefix: this is trial evidence, and a truncation
        # described as "SHA-256" would overstate what it proves.
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

        logger.info(
            "Reconnaissance complete: %d files, %d classified types, %d unavailable topics",
            len(files),
            len(classified),
            len(unavailable),
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={
                "recon_text": text,
                "recon_raw": raw,
                "unavailable": [u.as_dict() for u in unavailable],
                "recon_digest": digest,
            },
            phase=self.phase,
            confidence=1.0,
            duration_sec=time.monotonic() - start,
            metadata={
                "rationale": "Deterministic registry-driven reconnaissance over the bound target."
            },
        )

    def _collect_files(self, target: Path) -> list[str]:
        """Return every readable file as a sorted list of target-relative POSIX paths."""
        found: list[str] = []
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if _SKIP_DIR_PARTS & set(path.relative_to(target).parts):
                continue
            found.append(path.relative_to(target).as_posix())
        return sorted(found)

    def _load_type_globs(self) -> tuple[dict[str, list[str]], UnavailableTopic | None]:
        """Return {artifact_type_id: discovery globs} from the registry.

        A registry that cannot be read is reported as an unavailable topic rather
        than being treated as an empty registry -- an unreadable registry and one
        with no types are different facts, and only one of them is benign.
        """
        try:
            repository = self._repository or get_intent_repository()
            repository.initialize()
            refs = repository.list_artifact_types()
        except Exception as exc:
            logger.warning("Artifact-type registry unavailable: %s", exc)
            return {}, UnavailableTopic(
                topic="artifact_type_registry",
                reason=f"registry could not be loaded: {exc}",
            )

        return {ref.id: list(ref.content.get("discovery") or []) for ref in refs}, None

    def _classify(
        self, files: list[str], type_globs: dict[str, list[str]]
    ) -> tuple[dict[str, list[str]], list[str]]:
        """Match files against each type's discovery globs.

        A file may match several types -- the registry declares overlapping
        discovery by design (ADR-105) -- so membership is recorded per type and
        the unclassified list holds only files no type claimed.
        """
        classified: dict[str, list[str]] = {}
        claimed: set[str] = set()

        for type_id, globs in sorted(type_globs.items()):
            for pattern in globs:
                for rel in files:
                    if _matches(rel, pattern):
                        classified.setdefault(type_id, []).append(rel)
                        claimed.add(rel)

        for type_id in classified:
            classified[type_id] = sorted(set(classified[type_id]))

        return classified, [f for f in files if f not in claimed]

    def _layout(self, target: Path, files: list[str]) -> dict[str, int]:
        """Return {directory prefix: file count} to a fixed depth.

        The prefix is built from a file's directory parts only -- including the
        filename would turn every root-level or shallow file into its own
        one-entry 'directory' and bury the actual shape of the target.
        """
        layout: dict[str, int] = {}
        for rel in files:
            directories = rel.split("/")[:-1]
            prefix = "/".join(directories[:_LAYOUT_DEPTH]) if directories else "."
            layout[prefix] = layout.get(prefix, 0) + 1
        return dict(sorted(layout.items()))

    def _suffix_histogram(self, files: list[str]) -> dict[str, int]:
        """Return {suffix: count} for files no registered type claimed."""
        histogram: dict[str, int] = {}
        for rel in files:
            suffix = Path(rel).suffix or "(none)"
            histogram[suffix] = histogram.get(suffix, 0) + 1
        return dict(sorted(histogram.items(), key=lambda kv: (-kv[1], kv[0])))

    def _render(self, raw: dict[str, Any], unavailable: list[UnavailableTopic]) -> str:
        """Render the structured facts as the planner-facing report."""
        lines: list[str] = ["TARGET RECONNAISSANCE", ""]

        lines.append(f"Files observed: {raw['file_count']}")
        lines.append("")

        lines.append("Layout (path prefix -> file count):")
        for prefix, count in raw["layout"].items():
            lines.append(f"  {prefix}: {count}")
        if not raw["layout"]:
            lines.append("  (none)")
        lines.append("")

        lines.append("Governed artifact types present:")
        for type_id, count in raw["artifact_types_present"].items():
            examples = ", ".join(raw["artifact_type_examples"].get(type_id, []))
            lines.append(f"  {type_id}: {count} ({examples})")
        if not raw["artifact_types_present"]:
            lines.append("  (none -- no file matched any registered type)")
        lines.append("")

        lines.append(f"Unclassified files: {raw['unclassified_count']}")
        for suffix, count in list(raw["unclassified_suffixes"].items())[:10]:
            lines.append(f"  {suffix}: {count}")
        lines.append("")

        lines.append("Not observable (explicit absences):")
        for item in unavailable:
            lines.append(f"  {item.topic}: {item.reason}")
        if not unavailable:
            lines.append("  (none)")

        return "\n".join(lines)


def _matches(rel_path: str, pattern: str) -> bool:
    """Match a target-relative path against a discovery glob.

    ``**`` spans directories, so a plain fnmatch is applied to the whole path
    after normalising the recursive segment -- fnmatch's ``*`` already crosses
    ``/``, which is what the registry's globs assume.
    """
    normalised = pattern.replace("**/", "*").replace("**", "*")
    return fnmatch.fnmatch(rel_path, normalised)
