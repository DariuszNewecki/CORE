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

import ast
import builtins
import importlib
import inspect
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from shared.infrastructure.intent.cognitive_roles import load_cognitive_roles
from shared.infrastructure.intent.errors import GovernanceError
from shared.infrastructure.intent.filesystem_operations import (
    FilesystemOperationTaxonomyError,
    load_filesystem_operations,
)
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.intent.vocabulary_projection import (
    VOCABULARY_JSON_REL,
    VOCABULARY_PAPER_REL,
    VocabularyProjection,
    VocabularyProjectionError,
    compute_canonical_section_hash,
    load_vocabulary_projection,
    locate_canonical_section,
    normalize_vocabulary_cell,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


logger = getLogger(__name__)

# Providers are infrastructure. They must not appear in model.yaml.
_KNOWN_PROVIDERS = {"anthropic", "openai", "deepseek", "ollama", "azure", "mistral"}

# Cognitive role names are loaded fail-closed from
# .intent/taxonomies/cognitive_roles.yaml (ADR-068 taxonomy pattern). See
# load_cognitive_roles for the contract; the gate never carries a literal
# role set, so role declarations land by editing the taxonomy, not this file.

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

_GOVERNANCE_CHECK_TYPES = frozenset(
    {
        "all_rules_mapped",
        "active_routing_claimed_by_action",
        "namespace_has_drainer",
        "namespace_manifest_completeness",
        "fs_operations_completeness",
    }
)

_AUTO_REMEDIATION_REL = ".intent/enforcement/remediation/auto_remediation.yaml"
_RULES_DIR_REL = ".intent/rules"
_BODY_ATOMIC_REL = "src/body/atomic"
_DRAINER_REGISTRY_REL = ".intent/enforcement/quarantine/drainer_registry.yaml"
_NAMESPACE_MANIFEST_REL = ".intent/governance/namespace_manifest.yaml"
_NAMESPACE_GOVERNED_ROOTS = (".intent", ".specs")
_MAPPING_KEY_RE = re.compile(r"^  ([a-z][a-z0-9_.]+):$", re.MULTILINE)

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
                "authoritative_paper": normalize_vocabulary_cell(cells[3]),
            }
        )
    return terms, None


# -----------------------------------------------------------------------------
# Vocabulary check functions (module-level — pure, no instance state).
# Kept out of ArtifactGateEngine so the class stays under modularity limits.
# -----------------------------------------------------------------------------

_ENGINE_ID = "artifact_gate"


# ID: 7e3b9c2f-4a18-4d65-b083-1f5a8c6e2d40
def _result_to_findings(
    result: EngineResult, check_type: str, engine_id: str
) -> list[AuditFinding]:
    """Convert an EngineResult into AuditFindings for context-level dispatch.

    ADR-076 D3. The repo-level check_* functions return EngineResult
    (their per-file dispatch shape); ``verify_context`` must return
    ``list[AuditFinding]`` per the rule_executor contract for
    context-level rules. Severity is a placeholder — rule_executor
    overwrites it from the rule's declared enforcement.
    """
    if result.ok:
        return []
    findings: list[AuditFinding] = []
    for v in result.violations:
        if isinstance(v, dict):
            msg = str(v.get("message", ""))
            details = dict(v.get("details") or {})
        else:
            msg = str(v)
            details = {}
        findings.append(
            AuditFinding(
                check_id=f"{engine_id}.{check_type}",
                severity=AuditSeverity.INFO,
                message=msg,
                file_path="repo",
                context=details,
            )
        )
    return findings


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


# ID: 7d1a2c8e-4b3f-4d52-a6e1-9c2b8d4e1f7a
def _check_all_rules_mapped(repo_root: Path, check: str) -> EngineResult:
    """Verify every active reporting rule has an entry in auto_remediation.yaml.

    ADR-066: rules with no remediation-map entry produce a silent
    abandoned-finding re-emission loop. Scope is reporting rules only
    — blocking rules fire pre-commit and do not enter the audit loop.
    """
    map_file = repo_root / _AUTO_REMEDIATION_REL
    rules_dir = repo_root / _RULES_DIR_REL

    if not map_file.exists():
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: auto_remediation.yaml missing at {map_file}",
            violations=[f"Configuration error: {_AUTO_REMEDIATION_REL} not found"],
            engine_id=_ENGINE_ID,
        )
    if not rules_dir.is_dir():
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: rules dir missing at {rules_dir}",
            violations=[f"Configuration error: {_RULES_DIR_REL} not found"],
            engine_id=_ENGINE_ID,
        )

    repo = get_intent_repository()
    mapped_ids: set[str] = set(
        _MAPPING_KEY_RE.findall(
            repo.load_text(_AUTO_REMEDIATION_REL.removeprefix(".intent/"))
        )
    )

    unmapped: list[str] = []
    for ref in sorted(repo.list_policies(), key=lambda r: r.policy_id):
        if not ref.policy_id.startswith("rules/"):
            continue
        if ref.path.suffix != ".json":
            continue
        try:
            doc = repo.load_document(ref.path)
        except GovernanceError:
            # Defensive: a malformed rule document is a separate failure mode,
            # not this rule's concern. Skip silently — other validators flag it.
            continue
        if not isinstance(doc, dict):
            continue
        if doc.get("metadata", {}).get("status") != "active":
            continue
        for r in doc.get("rules", []) or []:
            if not isinstance(r, dict):
                continue
            rid = r.get("id")
            if not isinstance(rid, str) or not rid:
                continue
            if r.get("enforcement") != "reporting":
                continue
            if rid in mapped_ids:
                continue
            unmapped.append(rid)

    if not unmapped:
        return _vocab_result(check, [])

    violations = [
        f"Active reporting rule '{rid}' has no entry in {_AUTO_REMEDIATION_REL}"
        for rid in sorted(unmapped)
    ]
    return _vocab_result(check, violations)


def _extract_register_action_remediates(
    atomic_dir: Path,
) -> dict[str, set[str]]:
    """Walk src/body/atomic/**/*.py AST-only and extract
    ``{action_id → set(remediates)}`` from every ``@register_action(...)`` call.

    Mind-layer clean: reads source as text, parses with ast, does not import
    body code. Matches decorator calls where ``func`` is the bare name
    ``register_action`` (the canonical import shape in body/atomic/*.py).
    Aliased imports (``register_action as ra``) would not be matched and
    would surface as a missing action — that is an acceptable false-loud
    signal (no such alias exists in the tree at the time of writing).
    """
    out: dict[str, set[str]] = {}
    for py in sorted(atomic_dir.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                if not (
                    isinstance(deco.func, ast.Name)
                    and deco.func.id == "register_action"
                ):
                    continue
                action_id: str | None = None
                remediates: set[str] = set()
                for kw in deco.keywords:
                    if kw.arg == "action_id" and isinstance(kw.value, ast.Constant):
                        if isinstance(kw.value.value, str):
                            action_id = kw.value.value
                    elif kw.arg == "remediates" and isinstance(kw.value, ast.List):
                        for elt in kw.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                elt.value, str
                            ):
                                remediates.add(elt.value)
                if action_id is None:
                    continue
                # Merge with any prior collection — a single action_id may
                # appear in multiple files only if there is a registration
                # bug (already caught by atomic_actions rules); union here
                # is defensive but does not mask the duplication.
                out.setdefault(action_id, set()).update(remediates)
    return out


# ID: 4b0a3793-7764-49ee-8b4c-792bfac236e9
def _check_active_routing_claimed_by_action(
    repo_root: Path, check: str
) -> EngineResult:
    """Verify every ACTIVE auto_remediation.yaml entry's action declares the rule.

    For each entry under ``mappings:`` with ``status: ACTIVE`` and an
    ``action:`` field (flow: entries are exempt — see rule statement),
    verify the action's ``@register_action(remediates=[…])`` declaration
    in src/body/atomic/**/*.py claims the routed rule_id.

    Pairs with ``governance.remediation.all_rules_mapped``: that rule
    ensures every reporting rule has SOME entry; this rule ensures every
    ACTIVE entry is honored by its action (issue #580, ADR-095 D5).
    """
    map_file = repo_root / _AUTO_REMEDIATION_REL
    atomic_dir = repo_root / _BODY_ATOMIC_REL

    if not map_file.exists():
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: auto_remediation.yaml missing at {map_file}",
            violations=[f"Configuration error: {_AUTO_REMEDIATION_REL} not found"],
            engine_id=_ENGINE_ID,
        )
    if not atomic_dir.is_dir():
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: atomic dir missing at {atomic_dir}",
            violations=[f"Configuration error: {_BODY_ATOMIC_REL} not found"],
            engine_id=_ENGINE_ID,
        )

    try:
        doc = yaml.safe_load(map_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: cannot load auto_remediation.yaml: {exc}",
            violations=[f"Parse error: {exc}"],
            engine_id=_ENGINE_ID,
        )

    mappings = (doc or {}).get("mappings") if isinstance(doc, dict) else None
    if not isinstance(mappings, dict):
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: auto_remediation.yaml has no mappings: dict",
            violations=[
                "Structural error: top-level 'mappings:' is missing or not a mapping"
            ],
            engine_id=_ENGINE_ID,
        )

    remediates_by_action = _extract_register_action_remediates(atomic_dir)

    violations: list[str] = []
    for rule_id, entry in mappings.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "ACTIVE":
            continue
        action_id = entry.get("action")
        if not isinstance(action_id, str) or not action_id:
            # flow: entries (or malformed entries with neither) are exempt
            continue
        claimed = remediates_by_action.get(action_id)
        if claimed is None:
            violations.append(
                f"ACTIVE entry '{rule_id}' routes to action '{action_id}', "
                f"but no @register_action(action_id='{action_id}', ...) declaration "
                f"was found in {_BODY_ATOMIC_REL}/."
            )
            continue
        if rule_id not in claimed:
            violations.append(
                f"ACTIVE entry '{rule_id}' routes to action '{action_id}', "
                f"but '{action_id}'s @register_action(remediates=[…]) does not "
                f"claim '{rule_id}'. Either add '{rule_id}' to the action's "
                f"remediates list, or flip the entry to status: DELEGATE / PENDING."
            )

    return _vocab_result(check, sorted(violations))


# ID: 5b8c2d1e-7a4f-4609-bc3a-d8e9f0a1b234
async def _check_namespace_has_drainer(
    repo_root: Path,
    check: str,
    params: dict[str, Any],
) -> EngineResult:
    """Verify every awaiting_reaudit subject namespace has a registered drainer.

    ADR-072. The check enumerates DISTINCT subject prefixes currently
    held in ``awaiting_reaudit`` and compares them to the prefixes
    registered in ``drainer_registry.yaml``. A prefix present in the
    DB but absent from the registry is an unmapped quarantine namespace.

    DB access uses the audit-driver-injected session via
    ``params['_context'].db_session`` (mirrors llm_gate's pattern —
    Mind layer cannot open sessions itself). If no session is injected
    (e.g. IntentGuard pre-commit path), the check returns ok=True with
    a deferred-to-audit-time message rather than failing — the check
    is meaningful only when the live blackboard state is accessible.
    """
    from sqlalchemy import text

    registry_file = repo_root / _DRAINER_REGISTRY_REL
    if not registry_file.exists():
        return EngineResult(
            ok=False,
            message=(
                f"artifact_gate[{check}]: drainer_registry.yaml missing at "
                f"{registry_file}"
            ),
            violations=[f"Configuration error: {_DRAINER_REGISTRY_REL} not found"],
            engine_id=_ENGINE_ID,
        )

    repo = get_intent_repository()
    try:
        registry_doc = repo.load_document(
            repo.resolve_rel(_DRAINER_REGISTRY_REL.removeprefix(".intent/"))
        )
    except GovernanceError as exc:
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: cannot load drainer_registry.yaml: {exc}",
            violations=[f"Configuration error: {_DRAINER_REGISTRY_REL} unloadable"],
            engine_id=_ENGINE_ID,
        )

    if not isinstance(registry_doc, dict):
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: drainer_registry.yaml not a mapping",
            violations=[
                f"Configuration error: {_DRAINER_REGISTRY_REL} top-level "
                "must be a YAML mapping"
            ],
            engine_id=_ENGINE_ID,
        )

    raw_entries = registry_doc.get("namespaces") or []
    registered_normalized: set[str] = set()
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        prefix = entry.get("prefix")
        if isinstance(prefix, str) and prefix:
            # Normalise by stripping trailing colons so both "python::"
            # and "python" registry forms match the bare namespace returned
            # by SPLIT_PART.
            registered_normalized.add(prefix.rstrip(":"))

    # DB session is injected by the audit driver; absence is a
    # degraded-mode signal, not a check failure (see docstring).
    auditor_context = params.get("_context")
    session = getattr(auditor_context, "db_session", None)
    if session is None:
        return EngineResult(
            ok=True,
            message=(
                f"artifact_gate[{check}]: DB session not injected — check "
                "deferred to audit-time run that injects auditor_context.db_session."
            ),
            violations=[],
            engine_id=_ENGINE_ID,
        )

    result = await session.execute(
        text(
            """
            SELECT DISTINCT SPLIT_PART(subject, '::', 1) AS namespace
            FROM core.blackboard_entries
            WHERE entry_type = 'finding'
              AND status = 'awaiting_reaudit'
              AND resolved_at IS NULL
            """
        )
    )
    quarantine_namespaces = {row[0] for row in result.fetchall() if row[0]}

    unmapped = sorted(quarantine_namespaces - registered_normalized)
    if not unmapped:
        return EngineResult(
            ok=True,
            message=f"artifact_gate[{check}]: all quarantine namespaces have registered drainers.",
            violations=[],
            engine_id=_ENGINE_ID,
        )

    violations = [
        f"Subject namespace '{ns}' has rows in awaiting_reaudit but no "
        f"drainer is registered in {_DRAINER_REGISTRY_REL}"
        for ns in unmapped
    ]
    return EngineResult(
        ok=False,
        message=(
            f"artifact_gate[{check}]: {len(unmapped)} unmapped quarantine "
            "namespace(s) — ADR-072 invariant violated."
        ),
        violations=violations,
        engine_id=_ENGINE_ID,
    )


# ID: 742276f9-7865-4073-a345-1256089d91c8
def _check_namespace_manifest_completeness(repo_root: Path, check: str) -> EngineResult:
    """Verify every file under .intent/ and .specs/ has a manifest entry.

    ADR-075 D7. The check is a structural set-difference between the
    filesystem walk under the governed roots (.intent/ + .specs/) and the
    paths declared in .intent/governance/namespace_manifest.yaml's
    ``classifications`` list. A file present on disk with no manifest
    entry is unclassified and surfaces as a violation under this rule.
    """
    manifest_file = repo_root / _NAMESPACE_MANIFEST_REL
    if not manifest_file.exists():
        return EngineResult(
            ok=False,
            message=(
                f"artifact_gate[{check}]: namespace_manifest.yaml missing at "
                f"{manifest_file}"
            ),
            violations=[f"Configuration error: {_NAMESPACE_MANIFEST_REL} not found"],
            engine_id=_ENGINE_ID,
        )

    try:
        manifest_doc = yaml.safe_load(manifest_file.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: cannot parse namespace_manifest.yaml: {exc}",
            violations=[f"Configuration error: {_NAMESPACE_MANIFEST_REL} unparseable"],
            engine_id=_ENGINE_ID,
        )

    if not isinstance(manifest_doc, dict):
        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check}]: namespace_manifest.yaml not a mapping",
            violations=[
                f"Configuration error: {_NAMESPACE_MANIFEST_REL} top-level "
                "must be a YAML mapping"
            ],
            engine_id=_ENGINE_ID,
        )

    classified: set[str] = set()
    for entry in manifest_doc.get("classifications") or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            classified.add(path)

    fs_paths: set[str] = set()
    for root_name in _NAMESPACE_GOVERNED_ROOTS:
        root_dir = repo_root / root_name
        if not root_dir.is_dir():
            continue
        for p in root_dir.rglob("*"):
            if p.is_file():
                fs_paths.add(str(p.relative_to(repo_root)))

    unclassified = sorted(fs_paths - classified)
    if not unclassified:
        return _vocab_result(check, [])

    violations = [
        f"File '{path}' has no entry in {_NAMESPACE_MANIFEST_REL}"
        for path in unclassified
    ]
    return _vocab_result(check, violations)


# ID: f68dc080-017d-42ee-8580-095b44bf668d
def _check_fs_operations_completeness(repo_root: Path, check: str) -> EngineResult:
    """Verify the filesystem-operation taxonomy covers the runtime FS surface.

    ADR-077 §3. Three-part introspective set-difference against the loaded
    taxonomy:

    - Every public method on pathlib.Path must appear in operations.pathlib_path
      (auto-discovery; absence is a finding). Stale declarations whose names no
      longer resolve to runtime Path methods are also surfaced.
    - Every entry in operations.watched must still resolve to a callable in its
      module (catches stdlib rename/removal or third-party absence). Mixed
      namespaces (os/shutil/tempfile/builtin open) are not auto-discovered —
      §3 explicitly excludes that.
    - The taxonomy's declared python_version must match runtime major.minor
      (§5 determinism anchor).

    Remediation is manual_review per §3: classifying a newly surfaced call is a
    governance decision (read vs write), not auto-remediation territory.
    """
    try:
        taxonomy = load_filesystem_operations(repo_root)
    except FilesystemOperationTaxonomyError as exc:
        return EngineResult(
            ok=False,
            message=(
                f"artifact_gate[{check}]: filesystem-operation taxonomy failed to load."
            ),
            violations=[f"Taxonomy load error: {exc}"],
            engine_id=_ENGINE_ID,
        )

    violations: list[str] = []

    declared_pathlib = {entry.name for entry in taxonomy.pathlib_path}
    discovered_pathlib = {
        name
        for name, _ in inspect.getmembers(Path, predicate=callable)
        if not name.startswith("_")
    }
    for name in sorted(discovered_pathlib - declared_pathlib):
        violations.append(
            f"pathlib.Path public method '{name}' is present in the runtime "
            f"but absent from filesystem_operations.yaml "
            f"operations.pathlib_path — classify it (manual_review)."
        )
    for name in sorted(declared_pathlib - discovered_pathlib):
        violations.append(
            f"filesystem_operations.yaml operations.pathlib_path declares "
            f"'{name}' which is not a public method on pathlib.Path in this "
            f"runtime — remove the stale entry or re-verify against the "
            f"declared python_version (ADR-077 §5)."
        )

    for entry in sorted(taxonomy.watched, key=lambda e: e.name):
        ok, reason = _resolve_watched_call(entry.name)
        if not ok:
            violations.append(
                f"watched filesystem operation '{entry.name}' does not resolve "
                f"to a callable: {reason} — update the taxonomy or restore the "
                f"sanctioned import (manual_review)."
            )

    runtime_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if taxonomy.python_version != runtime_version:
        violations.append(
            f"filesystem_operations.yaml declares python_version "
            f"'{taxonomy.python_version}' but runtime is '{runtime_version}'; "
            f"re-verify classifications against {runtime_version} and update "
            f"the taxonomy header (ADR-077 §5)."
        )

    return _vocab_result(check, violations)


# ID: 269e97f0-0707-479c-b005-a3c23cd8a017
def _resolve_watched_call(qualified: str) -> tuple[bool, str]:
    """Resolve a dotted module.attr name (or bare builtin) to a callable.

    Returns ``(True, "")`` on success; ``(False, reason)`` on any failure.
    Bare names (no dot) resolve against ``builtins`` — e.g. ``"open"`` →
    ``builtins.open``. Dotted names import the leftmost segment and walk
    ``getattr`` through the remainder.
    """
    if "." not in qualified:
        target = getattr(builtins, qualified, None)
        if target is None:
            return False, f"builtins.{qualified} not found"
        if not callable(target):
            return False, f"builtins.{qualified} is not callable"
        return True, ""

    head, _, rest = qualified.partition(".")
    try:
        module = importlib.import_module(head)
    except ImportError as exc:
        return False, f"cannot import module '{head}': {exc}"

    obj: Any = module
    path_so_far = head
    for part in rest.split("."):
        obj = getattr(obj, part, None)
        path_so_far = f"{path_so_far}.{part}"
        if obj is None:
            return False, f"{path_so_far} not found"
    if not callable(obj):
        return False, f"{qualified} is not callable"
    return True, ""


# ID: 69841a82-0920-480c-94cb-d5e4b6cb50dd
class ArtifactGateEngine(BaseEngine):
    """
    Constitutional validator for PromptModel artifact manifests.

    Checks model.yaml files for structural completeness and abstraction
    boundary compliance. All checks are purely mechanical — no LLM involved.
    """

    engine_id = "artifact_gate"

    @classmethod
    # ID: 3c7b9d12-58a4-4e6f-8c1d-2a9e6b4f3d70
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """
        ADR-076 D1/D2/D3: artifact_gate is mixed-mode.

        Seven repo-level check_types (vocabulary projection/canonical_format/
        authoritative_paths + governance all_rules_mapped/namespace_has_drainer/
        namespace_manifest_completeness/fs_operations_completeness) dispatch
        context-level. The three PromptModel check_types (required_fields,
        no_provider_leak, role_abstraction) dispatch per-file over
        var/prompts/**/model.yaml.
        """
        if check_type is None:
            return False
        return (
            check_type in _VOCABULARY_CHECK_TYPES
            or check_type in _GOVERNANCE_CHECK_TYPES
        )

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

        # Governance meta-checks (ADR-066, ADR-072): repo-level invariants
        # over .intent/ content and blackboard state. Dispatched before YAML
        # load for the same reason.
        if check_type in _GOVERNANCE_CHECK_TYPES:
            return await self._check_governance(file_path, check_type, params)

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
        else:
            known_roles = load_cognitive_roles()
            if role not in known_roles:
                violations.append(
                    f"role '{role}' is not a declared cognitive role. "
                    f"Known roles: {sorted(known_roles)}. "
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

    # -------------------------------------------------------------------------
    # Governance meta-checks (ADR-066)
    # Dispatch only — the actual check functions live at module level so the
    # class stays under modularity.class_too_large limits.
    # -------------------------------------------------------------------------

    async def _check_governance(
        self, file_path: Path, check_type: str, params: dict[str, Any]
    ) -> EngineResult:
        """Locate the repo root from file_path and dispatch the governance check.

        Dispatcher is async because ``namespace_has_drainer`` (ADR-072 D4)
        runs a DB query via the injected auditor_context.db_session.
        ``all_rules_mapped`` remains synchronous internally.
        """
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

        if check_type == "all_rules_mapped":
            return _check_all_rules_mapped(repo_root, check_type)
        if check_type == "active_routing_claimed_by_action":
            return _check_active_routing_claimed_by_action(repo_root, check_type)
        if check_type == "namespace_has_drainer":
            return await _check_namespace_has_drainer(repo_root, check_type, params)
        if check_type == "namespace_manifest_completeness":
            return _check_namespace_manifest_completeness(repo_root, check_type)
        if check_type == "fs_operations_completeness":
            return _check_fs_operations_completeness(repo_root, check_type)

        return EngineResult(
            ok=False,
            message=f"artifact_gate[{check_type}]: dispatch fall-through.",
            violations=[f"Unknown governance check_type '{check_type}'"],
            engine_id=self.engine_id,
        )

    # -------------------------------------------------------------------------
    # Context-level dispatch (ADR-076 D3)
    # -------------------------------------------------------------------------

    # ID: 5a8d2f17-3e6b-4f12-9a47-c1b8e0d5f3a9
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Dispatch the six repo-level check_types over AuditorContext.

        ADR-076 D3. The three vocabulary checks and three governance
        meta-checks (ADR-066/072/075) walk the whole repository — they
        ignore ``file_path`` in their per-file form. This entry point
        runs them once per audit with ``context.repo_path`` as the
        repo root, instead of forcing the dispatcher to walk a synthetic
        file just so ``verify(file_path, ...)`` could parent-traverse
        back to the repo root.

        Returns ``list[AuditFinding]`` (the rule_executor contract for
        context-level), not ``EngineResult``. ``rule_executor`` overwrites
        severity per the rule's enforcement; check_id is derived from the
        check_type so the audit verdict surfaces the right rule.
        """
        check_type = params.get("check_type")
        if check_type is None:
            return [
                AuditFinding(
                    check_id=f"{self.engine_id}.error",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"{self.engine_id}.verify_context invoked without "
                        "params['check_type']."
                    ),
                    file_path="none",
                )
            ]

        repo_root = context.repo_path

        if check_type in _VOCABULARY_CHECK_TYPES:
            if check_type == "vocabulary_projection_consistency":
                result = _check_projection_consistency(repo_root, check_type)
            elif check_type == "vocabulary_canonical_format":
                result = _check_canonical_format(repo_root, check_type)
            elif check_type == "vocabulary_authoritative_paths":
                result = _check_authoritative_paths(repo_root, check_type)
            else:
                result = EngineResult(
                    ok=False,
                    message=f"{self.engine_id}[{check_type}]: dispatch fall-through.",
                    violations=[f"Unknown vocabulary check_type '{check_type}'"],
                    engine_id=self.engine_id,
                )
        elif check_type in _GOVERNANCE_CHECK_TYPES:
            if check_type == "all_rules_mapped":
                result = _check_all_rules_mapped(repo_root, check_type)
            elif check_type == "active_routing_claimed_by_action":
                result = _check_active_routing_claimed_by_action(repo_root, check_type)
            elif check_type == "namespace_has_drainer":
                merged_params = {**params, "_context": context}
                result = await _check_namespace_has_drainer(
                    repo_root, check_type, merged_params
                )
            elif check_type == "namespace_manifest_completeness":
                result = _check_namespace_manifest_completeness(repo_root, check_type)
            elif check_type == "fs_operations_completeness":
                result = _check_fs_operations_completeness(repo_root, check_type)
            else:
                result = EngineResult(
                    ok=False,
                    message=f"{self.engine_id}[{check_type}]: dispatch fall-through.",
                    violations=[f"Unknown governance check_type '{check_type}'"],
                    engine_id=self.engine_id,
                )
        else:
            return [
                AuditFinding(
                    check_id=f"{self.engine_id}.{check_type}.error",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"{self.engine_id}.verify_context received non-context-level "
                        f"check_type '{check_type}'. Per-file check_types route "
                        "through verify(file_path, ...)."
                    ),
                    file_path="none",
                )
            ]

        return _result_to_findings(result, check_type, self.engine_id)

    # The actual vocabulary check implementations live as module-level
    # functions (_check_projection_consistency, _check_canonical_format,
    # _check_authoritative_paths, _validate_authoritative_path, _vocab_result)
    # above the class declaration. Keeping them out of the class keeps it
    # under the modularity.class_too_large threshold.
