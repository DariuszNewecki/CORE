# src/mind/logic/engines/artifact_gate.py

"""
Constitutional Artifact Gate — PromptModel manifest validator.

Enforces structural and abstraction-boundary rules on var/prompts/*/model.yaml
files. Every check is deterministic: no LLM, no I/O beyond reading the file
already provided by the auditor.

Rules enforced:
- ai.prompt.artifact.required_fields   — id, version, role, input.required,
                                         output.format, success_criteria
- ai.prompt.artifact.no_provider_leak  — model.preference must not name an
                                         infrastructure provider
- ai.prompt.artifact.role_abstraction  — role field must reference a cognitive
                                         role, not a product or tool name

Vocabulary checks (ADR-023) operate on .specs/papers/CORE-Vocabulary.md and
.intent/META/vocabulary.json, not on YAML manifests. They are dispatched
before the YAML load so the engine never tries to parse Markdown as YAML.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from shared.infrastructure.intent.vocabulary_projection import (
    VOCABULARY_JSON_REL,
    VOCABULARY_PAPER_REL,
    VocabularyProjection,
    VocabularyProjectionError,
    compute_canonical_section_hash,
    load_vocabulary_projection,
    locate_canonical_section,
)
from shared.logger import getLogger

from .base import BaseEngine, EngineResult


logger = getLogger(__name__)

# Providers are infrastructure. They must not appear in model.yaml.
_KNOWN_PROVIDERS = {"anthropic", "openai", "deepseek", "ollama", "azure", "mistral"}

# Cognitive roles declared in .intent/. Extend as new roles are declared.
_KNOWN_ROLES = {
    "LocalCoder",
    "Architect",
    "Planner",
    "IntentTranslator",
    "DocstringWriter",
    "CapabilityTagger",
    "CodeReviewer",
    "RefactoringArchitect",
    "GPTArchitect",
    "LocalReasoner",
}

_REQUIRED_TOP_LEVEL = {"id", "version", "role", "success_criteria"}
_REQUIRED_INPUT_SUBFIELDS = {"required"}
_REQUIRED_OUTPUT_SUBFIELDS = {"format"}

_VOCABULARY_CHECK_TYPES = frozenset(
    {
        "vocabulary_projection_consistency",
        "vocabulary_canonical_format",
        "vocabulary_authoritative_paths",
    }
)

_REQUIRED_VOCAB_COLUMNS = ("term", "definition", "not", "authoritative_paper")
_GOVERNED_ROOTS = (".specs", ".intent")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s\-|]+\|$")


def _split_table_row(row: str) -> list[str]:
    """Parse one Markdown pipe-table row into stripped cells.

    ``"| foo | bar |"`` → ``["foo", "bar"]``. Leading/trailing whitespace and
    the outer pipes are stripped before splitting on ``|``.
    """
    stripped = row.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")]


def _parse_canonical_terms(
    paper: Path,
) -> tuple[list[dict[str, str]], str | None]:
    """Parse the canonical-section table into a list of term dicts.

    Returns ``(terms, error)``. On any parse failure returns ``([], error)``.
    Each term dict has the four required column keys; rows with fewer than
    four cells are skipped (the canonical_format check reports them).
    """
    if not paper.is_file():
        return [], f"Canonical paper missing: {paper}"
    try:
        text = paper.read_text(encoding="utf-8")
    except OSError as exc:
        return [], f"Cannot read canonical paper {paper}: {exc}"

    rng = locate_canonical_section(text)
    if rng is None:
        return [], f"Canonical heading not found in {paper}"
    start, end = rng
    section_lines = text.splitlines()[start:end]
    table_rows = [line for line in section_lines if line.lstrip().startswith("|")]
    if len(table_rows) < 3:
        return [], (
            f"Canonical table needs header, separator, and at least one data "
            f"row; found {len(table_rows)} pipe row(s)."
        )

    sep_indices = [
        i for i, row in enumerate(table_rows) if _TABLE_SEPARATOR_RE.match(row.strip())
    ]
    if not sep_indices:
        return [], "Canonical table has no separator row."
    sep_idx = sep_indices[0]
    if sep_idx == 0:
        return [], "Separator row precedes header in canonical table."

    terms: list[dict[str, str]] = []
    for row in table_rows[sep_idx + 1 :]:
        cells = _split_table_row(row)
        if len(cells) < len(_REQUIRED_VOCAB_COLUMNS):
            continue
        terms.append(
            {
                "term": cells[0],
                "definition": cells[1],
                "not": cells[2],
                "authoritative_paper": cells[3],
            }
        )
    return terms, None


# -----------------------------------------------------------------------------
# Vocabulary check functions (module-level — pure, no instance state).
# Kept out of ArtifactGateEngine so the class stays under modularity limits.
# -----------------------------------------------------------------------------

_ENGINE_ID = "artifact_gate"


def _vocab_result(check: str, violations: list[str]) -> EngineResult:
    """EngineResult builder for vocabulary checks.

    Vocabulary checks span multiple files (paper + projection) so the
    message references the check_type, not a single file_path.
    """
    if not violations:
        return EngineResult(
            ok=True,
            message=f"artifact_gate[{check}]: passed.",
            violations=[],
            engine_id=_ENGINE_ID,
        )
    return EngineResult(
        ok=False,
        message=f"artifact_gate[{check}]: {len(violations)} violation(s).",
        violations=violations,
        engine_id=_ENGINE_ID,
    )


def _validate_authoritative_path(
    term: str, path: str, repo_root: Path, source: str
) -> list[str]:
    """Return violation strings for a single term's authoritative_paper value."""
    if not path:
        return [f"{source} term '{term}': authoritative_paper is empty."]
    if not any(path.startswith(root + "/") for root in _GOVERNED_ROOTS):
        return [
            f"{source} term '{term}': authoritative_paper '{path}' must "
            f"start with one of {list(_GOVERNED_ROOTS)} followed by '/'."
        ]
    if not (repo_root / path).is_file():
        return [
            f"{source} term '{term}': authoritative_paper '{path}' does not "
            "resolve to an existing file."
        ]
    return []


def _check_projection_consistency(repo_root: Path, check: str) -> EngineResult:
    """Cross-check canonical Markdown section against the JSON projection."""
    proj = load_vocabulary_projection(repo_root)
    if isinstance(proj, VocabularyProjectionError):
        return _vocab_result(check, [f"Projection broken: {proj.reason}"])
    assert isinstance(proj, VocabularyProjection)

    paper = repo_root / VOCABULARY_PAPER_REL
    canonical_terms, parse_err = _parse_canonical_terms(paper)
    if parse_err:
        return _vocab_result(check, [parse_err])

    canonical_names = {t["term"] for t in canonical_terms}
    projection_names = {t.term for t in proj.terms}

    violations: list[str] = []
    for name in sorted(canonical_names - projection_names):
        violations.append(
            f"Canonical term '{name}' is absent from projection {VOCABULARY_JSON_REL}."
        )
    for name in sorted(projection_names - canonical_names):
        violations.append(
            f"Projection term '{name}' is absent from canonical section "
            f"in {VOCABULARY_PAPER_REL}."
        )

    recomputed = compute_canonical_section_hash(repo_root)
    if recomputed is not None and recomputed != proj.source_hash:
        violations.append(
            "source_hash mismatch: projection has "
            f"'{proj.source_hash[:12]}', canonical section currently hashes "
            f"to '{recomputed[:12]}'. Regenerate the projection via "
            "sync_vocabulary."
        )

    return _vocab_result(check, violations)


def _check_canonical_format(repo_root: Path, check: str) -> EngineResult:
    """Validate the structural shape of the canonical-section Markdown table."""
    from shared.infrastructure.intent.vocabulary_projection import CANONICAL_HEADING

    paper = repo_root / VOCABULARY_PAPER_REL
    if not paper.is_file():
        return _vocab_result(
            check, [f"Canonical paper missing: {VOCABULARY_PAPER_REL}"]
        )

    text = paper.read_text(encoding="utf-8")
    lines = text.splitlines()

    violations: list[str] = []
    heading_count = sum(1 for line in lines if line.rstrip() == CANONICAL_HEADING)
    if heading_count == 0:
        violations.append(f"Canonical heading '{CANONICAL_HEADING}' not found.")
        return _vocab_result(check, violations)
    if heading_count > 1:
        violations.append(
            f"Canonical heading appears {heading_count} times; expected exactly 1."
        )

    rng = locate_canonical_section(text)
    if rng is None:
        violations.append("Canonical section could not be located.")
        return _vocab_result(check, violations)
    start, end = rng
    section_lines = lines[start:end]

    table_rows = [line for line in section_lines if line.lstrip().startswith("|")]
    if not table_rows:
        violations.append(
            "No Markdown table found in canonical section (no rows starting with '|')."
        )
        return _vocab_result(check, violations)

    sep_indices = [
        i for i, row in enumerate(table_rows) if _TABLE_SEPARATOR_RE.match(row.strip())
    ]
    if not sep_indices:
        violations.append("No separator row matching r'^\\|[\\s\\-|]+\\|$' found.")
        return _vocab_result(check, violations)
    if len(sep_indices) > 1:
        violations.append(
            f"Found {len(sep_indices)} separator rows in canonical section; "
            "expected exactly 1 (nested table not allowed)."
        )

    sep_idx = sep_indices[0]
    if sep_idx == 0:
        violations.append("Separator row precedes any header row.")
        return _vocab_result(check, violations)

    header_cells = _split_table_row(table_rows[sep_idx - 1])
    first_four = [c.lower() for c in header_cells[: len(_REQUIRED_VOCAB_COLUMNS)]]
    if first_four != list(_REQUIRED_VOCAB_COLUMNS):
        violations.append(
            "Header columns must start with "
            f"{list(_REQUIRED_VOCAB_COLUMNS)} in that order; "
            f"got {first_four}."
        )

    data_rows = table_rows[sep_idx + 1 :]
    for i, row in enumerate(data_rows, start=1):
        cells = _split_table_row(row)
        if len(cells) < len(_REQUIRED_VOCAB_COLUMNS):
            violations.append(
                f"Row {i}: has {len(cells)} cell(s); requires at least "
                f"{len(_REQUIRED_VOCAB_COLUMNS)}."
            )
            continue
        for col_idx, col_name in enumerate(_REQUIRED_VOCAB_COLUMNS):
            if not cells[col_idx]:
                violations.append(f"Row {i}: column '{col_name}' is empty.")
        for cell in cells:
            if "<" in cell and ">" in cell:
                violations.append(f"Row {i}: cell contains HTML markup: '{cell[:60]}'.")
                break
            if "![" in cell:
                violations.append(
                    f"Row {i}: cell contains an inline image: '{cell[:60]}'."
                )
                break

    return _vocab_result(check, violations)


def _check_authoritative_paths(repo_root: Path, check: str) -> EngineResult:
    """Verify each term's authoritative_paper resolves under a governed root."""
    paper = repo_root / VOCABULARY_PAPER_REL
    canonical_terms, parse_err = _parse_canonical_terms(paper)
    if parse_err:
        return _vocab_result(check, [parse_err])
    canonical_paths = {t["term"]: t["authoritative_paper"] for t in canonical_terms}

    proj = load_vocabulary_projection(repo_root)
    violations: list[str] = []
    projection_paths: dict[str, str] = {}
    if isinstance(proj, VocabularyProjectionError):
        violations.append(f"Projection broken: {proj.reason}")
    else:
        assert isinstance(proj, VocabularyProjection)
        projection_paths = {t.term: t.authoritative_paper for t in proj.terms}

    for term, path in canonical_paths.items():
        violations.extend(
            _validate_authoritative_path(term, path, repo_root, "canonical")
        )
    for term, path in projection_paths.items():
        violations.extend(
            _validate_authoritative_path(term, path, repo_root, "projection")
        )

    for term in sorted(set(canonical_paths) & set(projection_paths)):
        if canonical_paths[term] != projection_paths[term]:
            violations.append(
                f"Term '{term}': projection authoritative_paper "
                f"'{projection_paths[term]}' != canonical "
                f"'{canonical_paths[term]}'."
            )

    return _vocab_result(check, violations)


# ID: 69841a82-0920-480c-94cb-d5e4b6cb50dd
class ArtifactGateEngine(BaseEngine):
    """
    Constitutional validator for PromptModel artifact manifests.

    Checks model.yaml files for structural completeness and abstraction
    boundary compliance. All checks are purely mechanical — no LLM involved.
    """

    engine_id = "artifact_gate"

    # ID: 46226873-bc5a-4258-b3c8-476b0cfc878a
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Validate a model.yaml file against constitutional artifact rules.

        Dispatches to a specific check based on params['check_type'].
        Supported check types:
          - required_fields       — structural completeness
          - no_provider_leak      — preference field abstraction boundary
          - role_abstraction      — role field must be a cognitive role

        Args:
            file_path: Absolute path to the model.yaml being audited.
            params: Rule parameters from enforcement mapping.

        Returns:
            EngineResult with violations list; ok=True means compliant.
        """
        check_type = params.get("check_type", "required_fields")

        if not file_path.exists():
            return EngineResult(
                ok=False,
                message=f"Artifact file not found: {file_path}",
                violations=[f"Missing file: {file_path}"],
                engine_id=self.engine_id,
            )

        # Dispatch vocabulary checks BEFORE the YAML load. They operate on
        # Markdown + JSON, not on PromptModel manifests, and pass through
        # repo-level walks rather than reading file_path as YAML.
        if check_type in _VOCABULARY_CHECK_TYPES:
            return self._check_vocabulary(file_path, check_type)

        try:
            raw = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return EngineResult(
                ok=False,
                message=f"Cannot parse model.yaml: {exc}",
                violations=[f"YAML parse error in {file_path}: {exc}"],
                engine_id=self.engine_id,
            )

        if check_type == "required_fields":
            return self._check_required_fields(file_path, raw)
        if check_type == "no_provider_leak":
            return self._check_no_provider_leak(file_path, raw)
        if check_type == "role_abstraction":
            return self._check_role_abstraction(file_path, raw)

        return EngineResult(
            ok=False,
            message=f"Unknown artifact_gate check_type: {check_type}",
            violations=[f"Configuration error: unknown check_type '{check_type}'"],
            engine_id=self.engine_id,
        )

    # -------------------------------------------------------------------------
    # Checks
    # -------------------------------------------------------------------------

    # ID: 48ae4ead-2944-4c5a-8c8f-1423aad53497
    def _check_required_fields(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Verify all mandatory top-level and nested fields are present and
        non-empty in a model.yaml manifest.
        """
        violations: list[str] = []

        for field in _REQUIRED_TOP_LEVEL:
            if not manifest.get(field):
                violations.append(f"Missing or empty required field: '{field}'")

        input_block = manifest.get("input", {})
        if not isinstance(input_block, dict):
            violations.append("'input' must be a mapping")
        else:
            for sub in _REQUIRED_INPUT_SUBFIELDS:
                if sub not in input_block:
                    violations.append(f"Missing required field: 'input.{sub}'")

        output_block = manifest.get("output", {})
        if not isinstance(output_block, dict):
            violations.append("'output' must be a mapping")
        else:
            for sub in _REQUIRED_OUTPUT_SUBFIELDS:
                if sub not in output_block:
                    violations.append(f"Missing required field: 'output.{sub}'")

        return self._result(file_path, violations, "required_fields")

    # ID: 33aaf189-b193-4fd9-bf4f-951098928e29
    def _check_no_provider_leak(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Ensure model.yaml does not reference infrastructure providers in the
        model.preference field. Preference must name a capability class
        (e.g. 'local', 'fast') or be absent — never a product name.
        """
        violations: list[str] = []

        model_block = manifest.get("model", {})
        if isinstance(model_block, dict):
            preference = str(model_block.get("preference", "")).lower().strip()
            if preference in _KNOWN_PROVIDERS:
                violations.append(
                    f"model.preference '{preference}' names an infrastructure provider. "
                    "Use a capability class (e.g. 'local', 'fast') or remove the field. "
                    "Provider routing belongs in CognitiveService role configuration, "
                    "not in a prompt artifact."
                )

        return self._result(file_path, violations, "no_provider_leak")

    # ID: b984e44a-819b-4bc7-a0d9-e4272757002c
    def _check_role_abstraction(
        self, file_path: Path, manifest: dict[str, Any]
    ) -> EngineResult:
        """
        Verify the role field references a declared cognitive role, not a
        product, tool, or arbitrary string.
        """
        violations: list[str] = []

        role = str(manifest.get("role", "")).strip()
        if not role:
            violations.append("'role' field is missing or empty.")
        elif role not in _KNOWN_ROLES:
            violations.append(
                f"role '{role}' is not a declared cognitive role. "
                f"Known roles: {sorted(_KNOWN_ROLES)}. "
                "If this is a new role, declare it in .intent/ first."
            )

        return self._result(file_path, violations, "role_abstraction")

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _result(
        self, file_path: Path, violations: list[str], check: str
    ) -> EngineResult:
        """Build a standardised EngineResult for an artifact_gate check."""
        if not violations:
            return EngineResult(
                ok=True,
                message=f"artifact_gate[{check}]: {file_path.name} passed.",
                violations=[],
                engine_id=self.engine_id,
            )
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: {len(violations)} violation(s) in {file_path.name}.",
            violations=violations,
            engine_id=self.engine_id,
        )

    # -------------------------------------------------------------------------
    # Vocabulary checks (ADR-023)
    # Dispatch only — the actual check functions live at module level so the
    # class stays under modularity.class_too_large limits.
    # -------------------------------------------------------------------------

    def _check_vocabulary(self, file_path: Path, check_type: str) -> EngineResult:
        """Locate the repo root from file_path and dispatch the vocabulary check."""
        repo_root: Path | None = None
        for parent in file_path.resolve().parents:
            if (parent / ".intent").is_dir() and (parent / ".specs").is_dir():
                repo_root = parent
                break
        if repo_root is None:
            return EngineResult(
                ok=False,
                message=f"artifact_gate[{check_type}]: cannot locate repo root.",
                violations=[
                    f"Configuration error: walked up from {file_path} but found "
                    "no directory containing both .intent/ and .specs/."
                ],
                engine_id=self.engine_id,
            )

        if check_type == "vocabulary_projection_consistency":
            return _check_projection_consistency(repo_root, check_type)
        if check_type == "vocabulary_canonical_format":
            return _check_canonical_format(repo_root, check_type)
        if check_type == "vocabulary_authoritative_paths":
            return _check_authoritative_paths(repo_root, check_type)

        # Should never reach here — verify() filters check_type — but keep
        # a defensive return in case the dispatch table drifts.
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check_type}]: dispatch fall-through.",
            violations=[f"Unknown vocabulary check_type '{check_type}'"],
            engine_id=self.engine_id,
        )

    # The actual vocabulary check implementations live as module-level
    # functions (_check_projection_consistency, _check_canonical_format,
    # _check_authoritative_paths, _validate_authoritative_path, _vocab_result)
    # above the class declaration. Keeping them out of the class keeps it
    # under the modularity.class_too_large threshold.
