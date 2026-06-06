# src/mind/logic/engines/taxonomy_gate.py

"""
Taxonomy Gate Engine — context-level taxonomy invariants.

Hosts two cross-artifact taxonomy checks:

1. ``operational_capabilities_decorator_backing`` (ADR-079 D9) — every
   capability id in ``.intent/taxonomies/operational_capabilities.yaml``
   must be backed by exactly one ``@atomic_action(action_id="<id>")``
   decoration in ``src/``.

2. ``sensor_supported_by_declaration`` (ADR-091 D4) — every sensor worker
   declaration carrying ``mandate.scope.artifact_type`` must appear in
   that artifact_type's ``supported_sensors`` array, and vice versa. The
   authored set (artifact_type.supported_sensors) and the introspected
   set (sensor declarations) must be equal.

Both checks are cross-artifact (whole-YAML against another whole surface),
which is why they live in a context-level engine rather than under
``ast_gate``. The substrate is a live cross-surface sweep, not a single
file_path.

CONSTITUTIONAL ALIGNMENT:
- Async-first verify per the BaseEngine contract (ADR-076 D1/D2).
- Context-level dispatch for every check_type owned.
- Fail-soft on per-file parse errors (a single unparseable file must not
  crash the audit cycle — log and skip).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.intent.operational_capabilities import (
    OperationalCapabilityTaxonomyError,
    load_operational_capabilities,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver
from shared.processors.yaml_processor import strict_yaml_processor

from .base import BaseEngine, EngineResult


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


_DECORATOR_BACKING_CHECK = "operational_capabilities_decorator_backing"
_SENSOR_SUPPORT_CHECK = "sensor_supported_by_declaration"
_SELF_RESOLVE_RESOLVER_OWNED_CHECK = "self_resolve_resolver_owned"
_YAML_REL_PATH = ".intent/taxonomies/operational_capabilities.yaml"
_WORKERS_REL_DIR = ".intent/workers"
_ARTIFACT_TYPES_REL_DIR = ".intent/artifact_types"
_TESTS_REL_DIR = "tests"
_RESOLVER_DOCSTRING_BLOCK = "ADR-091 D2 Revision B resolution classification:"


# ID: 8c4e1f7b-2d6a-4b58-9e3c-1a7f6d4b5e89
class TaxonomyGateEngine(BaseEngine):
    """Context-level taxonomy invariant auditor.

    Hosts two cross-artifact checks:

    - ``operational_capabilities_decorator_backing`` (ADR-079 D9) —
      phantom-decoration invariant. A capability id in the YAML with no
      matching ``@atomic_action(action_id=<id>)`` decoration in ``src/``
      is a phantom — it cannot be authorized by the chokepoint because no
      caller can ever set ``_executor_token`` to it.

    - ``sensor_supported_by_declaration`` (ADR-091 D4) — sensor↔artifact_type
      coherence. The authored set (each artifact_type's
      ``supported_sensors``) and the introspected set (sensor worker
      declarations carrying ``mandate.scope.artifact_type``) must be
      equal. Sensor declarations without ``artifact_type`` are excluded
      from the introspected set during the Phase-1 transition window so
      the nine misclassified sensing-class workers do not surface as
      phantoms before #570 closes.

    Decorator-backing: stage 1 shipped at ``reporting``; promoted to
    ``blocking`` at ADR-079 D10 stage 2 (#495).

    Sensor support: ships at ``reporting`` per ADR-091 D5 Phase 1;
    promotes to ``blocking`` at Phase 7 once #570 closes.
    """

    engine_id = "taxonomy_gate"

    @classmethod
    # ID: f3a8d672-5c19-4e2b-b481-6d9e7f3a2c14
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """All three checks are cross-artifact, not per-file."""
        return check_type in (
            _DECORATOR_BACKING_CHECK,
            _SENSOR_SUPPORT_CHECK,
            _SELF_RESOLVE_RESOLVER_OWNED_CHECK,
        )

    def __init__(self, path_resolver: PathResolver) -> None:
        """Initialize with the audit's path resolver — used for the repo-root
        anchor when locating the YAML and AST-walking ``src/``."""
        self._path_resolver = path_resolver

    # ID: 2b9d4f6a-8e3c-4751-a16d-5b9e2d7f4c83
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Per-file path — this engine has no per-file checks.

        The auditor dispatches context-level rules through ``verify_context``
        (see ``rule_executor.py`` after the ``if rule.is_context_level:``
        gate). ``verify`` is reachable only if a rule were mis-mapped as
        per-file with this engine; surface that as an engine-not-ok signal
        rather than silently producing nothing.
        """
        check_type = params.get("check_type")
        return EngineResult(
            ok=False,
            message=(
                f"taxonomy_gate: check_type {check_type!r} is context-level; "
                f"dispatch via verify_context, not verify"
            ),
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: 19c8e74f-6ad3-4b91-95e7-2c43f8a9d6b1
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Context-level dispatch — the auditor calls this for any rule
        whose engine returns True from ``is_context_level_for(check_type)``.

        Returns one ``AuditFinding`` per phantom capability id. Severity
        is overwritten by the auditor from ``rule.enforcement``; the default
        here is INFO so a misconfigured caller still gets a non-blocking
        signal.
        """
        check_type = params.get("check_type")
        if check_type == _DECORATOR_BACKING_CHECK:
            return self._build_decorator_backing_findings(context.repo_path)
        if check_type == _SENSOR_SUPPORT_CHECK:
            return self._build_sensor_support_findings(context.repo_path)
        if check_type == _SELF_RESOLVE_RESOLVER_OWNED_CHECK:
            return self._build_self_resolve_findings(context.repo_path)
        return [
            AuditFinding(
                check_id="taxonomy_gate.unknown_check_type",
                severity=AuditSeverity.BLOCK,
                message=(
                    f"taxonomy_gate: unknown check_type {check_type!r}; "
                    f"valid values: {_DECORATOR_BACKING_CHECK!r}, "
                    f"{_SENSOR_SUPPORT_CHECK!r}, "
                    f"{_SELF_RESOLVE_RESOLVER_OWNED_CHECK!r}"
                ),
                file_path="none",
            )
        ]

    def _build_decorator_backing_findings(self, repo_root: Path) -> list[AuditFinding]:
        """Compute YAML-vs-decoration set difference; one finding per phantom."""
        try:
            capabilities = load_operational_capabilities(repo_root)
        except OperationalCapabilityTaxonomyError as exc:
            # Loader failure is a degraded-instrument state — emit one
            # finding under a distinct check_id so the operator sees the
            # underlying YAML defect rather than a phantom-shaped misattribution.
            return [
                AuditFinding(
                    check_id="governance.taxonomy.operational_capabilities_decorator_backing.load_failed",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"taxonomy_gate: cannot load operational-capability "
                        f"taxonomy: {exc}"
                    ),
                    file_path=_YAML_REL_PATH,
                )
            ]

        yaml_ids = {cap.id for cap in capabilities}
        decoration_ids = _collect_atomic_action_ids(repo_root / "src")
        phantoms = sorted(yaml_ids - decoration_ids)

        return [
            AuditFinding(
                check_id="governance.taxonomy.operational_capabilities_decorator_backing",
                severity=AuditSeverity.INFO,
                message=(
                    f"Phantom capability '{cap_id}' in "
                    f"{_YAML_REL_PATH} has no matching "
                    f"@atomic_action(action_id={cap_id!r}) decoration in src/. "
                    f"Resolve per ADR-079 D9: strip the YAML entry (Shape 1) "
                    f"or decorate the underlying function and re-route its "
                    f"dispatch through ActionExecutor.execute (Shape 2 — "
                    f"three-change recipe: @register_action + @atomic_action "
                    f"+ **kwargs)."
                ),
                file_path=_YAML_REL_PATH,
                context={"capability_id": cap_id},
            )
            for cap_id in phantoms
        ]

    def _build_sensor_support_findings(self, repo_root: Path) -> list[AuditFinding]:
        """Compute sensor↔artifact_type set difference; one finding per asymmetry.

        Per ADR-091 D4: the introspected set ``{(artifact_type_id, sensor_id)}``
        is built from every sensor worker declaration that carries
        ``mandate.scope.artifact_type``. The authored set is built from every
        artifact_type's ``supported_sensors`` array. The two sets must be equal.

        Sensor declarations without ``artifact_type`` are excluded from the
        introspected set during the Phase-1 transition window so the nine
        misclassified ``class: sensing`` workers (embedders, crawlers,
        transformers — tracked at #570) do not surface as phantoms before
        reclassification.
        """
        intent_repo = get_intent_repository()
        try:
            intent_repo.initialize()
        except Exception as exc:
            return [
                AuditFinding(
                    check_id=(
                        "governance.taxonomy.sensor_supported_by_declaration"
                        ".load_failed"
                    ),
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"taxonomy_gate: cannot initialize IntentRepository for "
                        f"sensor_supported_by_declaration: {exc}"
                    ),
                    file_path=_ARTIFACT_TYPES_REL_DIR,
                )
            ]

        authored: set[tuple[str, str]] = set()
        for ref in intent_repo.list_artifact_types():
            for sensor_id in ref.content.get("supported_sensors", []) or []:
                if isinstance(sensor_id, str) and sensor_id.strip():
                    authored.add((ref.id, sensor_id))

        introspected = _collect_sensor_artifact_pairs(repo_root / _WORKERS_REL_DIR)

        findings: list[AuditFinding] = []
        for artifact_type_id, sensor_id in sorted(introspected - authored):
            findings.append(
                AuditFinding(
                    check_id="governance.taxonomy.sensor_supported_by_declaration",
                    severity=AuditSeverity.INFO,
                    message=(
                        f"Sensor '{sensor_id}' declares artifact_type "
                        f"'{artifact_type_id}' but is not listed in that "
                        f"artifact_type's supported_sensors array. Per ADR-091 D4, "
                        f"the authored set must mirror the introspected set: add "
                        f"'{sensor_id}' to "
                        f".intent/artifact_types/{artifact_type_id}.yaml under "
                        f"supported_sensors."
                    ),
                    file_path=f"{_ARTIFACT_TYPES_REL_DIR}/{artifact_type_id}.yaml",
                    context={
                        "artifact_type_id": artifact_type_id,
                        "sensor_id": sensor_id,
                        "direction": "introspected_not_authored",
                    },
                )
            )
        for artifact_type_id, sensor_id in sorted(authored - introspected):
            findings.append(
                AuditFinding(
                    check_id="governance.taxonomy.sensor_supported_by_declaration",
                    severity=AuditSeverity.INFO,
                    message=(
                        f"artifact_type '{artifact_type_id}' lists sensor "
                        f"'{sensor_id}' in supported_sensors but no sensor "
                        f"declaration in .intent/workers/ declares "
                        f"mandate.scope.artifact_type containing "
                        f"'{artifact_type_id}'. Per ADR-091 D4 this is a phantom — "
                        f"either remove the supported_sensors entry or add the "
                        f"artifact_type to the sensor's mandate.scope."
                    ),
                    file_path=f"{_ARTIFACT_TYPES_REL_DIR}/{artifact_type_id}.yaml",
                    context={
                        "artifact_type_id": artifact_type_id,
                        "sensor_id": sensor_id,
                        "direction": "authored_not_introspected",
                    },
                )
            )
        return findings

    def _build_self_resolve_findings(self, repo_root: Path) -> list[AuditFinding]:
        """Compute the ADR-091 D2 Revision B (d) resolver-ownership findings.

        Every distinct subject prefix appearing on a
        post_finding(..., resolution_mechanism='self_resolve') call site in
        src/ MUST be backed by (1) a documented resolver path in the
        emitting worker's module docstring (the canonical
        "ADR-091 D2 Revision B resolution classification:" block) AND
        (2) at least one test under tests/ that references the subject prefix
        as a string.

        The check walks src/, builds a map
        {subject_prefix: set[emitting_module]}, then verifies both conditions
        over the union of each prefix's emitting modules — a prefix passes if
        ANY emitter carries the docstring block AND the prefix appears as a
        substring of any string in ANY test file. Generous signal per
        Revision B (h)'s scope-decision tolerance: a posting-side test that
        references the prefix is taken to exercise resolver ownership for
        that prefix, since Revision B (h) explicitly permits posting-only
        tests when full open → resolved integration is impractical.

        Emits one AuditFinding per uncovered prefix.
        """
        site_map = _collect_self_resolve_call_sites(repo_root / "src")
        tests_root = repo_root / _TESTS_REL_DIR

        findings: list[AuditFinding] = []
        for prefix, emitting_modules in sorted(site_map.items()):
            has_docstring = any(
                _module_docstring_has_canonical_block(mod) for mod in emitting_modules
            )
            has_test = _prefix_appears_in_tests(prefix, tests_root)
            if has_docstring and has_test:
                continue
            rep_module = sorted(emitting_modules)[0]
            try:
                rel_module = rep_module.relative_to(repo_root)
            except ValueError:
                rel_module = rep_module
            gaps: list[str] = []
            if not has_docstring:
                gaps.append("module docstring lacks the canonical resolver block")
            if not has_test:
                gaps.append("no test file references the subject prefix")
            module_list = sorted(
                str(m.relative_to(repo_root)) for m in emitting_modules
            )
            findings.append(
                AuditFinding(
                    check_id="governance.taxonomy.self_resolve_resolver_owned",
                    severity=AuditSeverity.INFO,
                    message=(
                        f"self_resolve subject prefix '{prefix}' is missing "
                        f"resolver-ownership backing: {' and '.join(gaps)}. "
                        f"Per ADR-091 D2 Revision B (d), every self_resolve "
                        f"emission must document its resolver path "
                        f"('{_RESOLVER_DOCSTRING_BLOCK}' block in the emitter's "
                        f"module docstring) and have at least one test "
                        f"referencing the subject prefix (or invoke the "
                        f"per-test scope-decision exemption per Revision B (h)). "
                        f"Emitting module(s): {', '.join(module_list)}."
                    ),
                    file_path=str(rel_module),
                    context={
                        "subject_prefix": prefix,
                        "missing_docstring_block": not has_docstring,
                        "missing_test_coverage": not has_test,
                        "emitting_modules": module_list,
                    },
                )
            )
        return findings


def _collect_sensor_artifact_pairs(workers_dir: Path) -> set[tuple[str, str]]:
    """Walk .intent/workers/*.yaml; emit (artifact_type_id, sensor_id) pairs.

    Sensor id is the YAML filename stem (e.g. ``audit_sensor_purity``) —
    matches ``declaration_name`` on the Worker base class. Declarations
    without ``class: sensing`` or without ``mandate.scope.artifact_type``
    contribute nothing (Phase 1 transition allowance for #570).
    """
    pairs: set[tuple[str, str]] = set()
    if not workers_dir.is_dir():
        return pairs
    for yaml_path in sorted(workers_dir.glob("*.yaml")):
        try:
            data = strict_yaml_processor.load_strict(yaml_path)
        except Exception as exc:
            logger.debug("taxonomy_gate: cannot load %s: %s", yaml_path, exc)
            continue
        if not isinstance(data, dict):
            continue
        identity = data.get("identity") or {}
        if identity.get("class") != "sensing":
            continue
        scope = (data.get("mandate") or {}).get("scope") or {}
        artifact_types = scope.get("artifact_type")
        if not isinstance(artifact_types, list):
            continue
        sensor_id = yaml_path.stem
        for artifact_type_id in artifact_types:
            if isinstance(artifact_type_id, str) and artifact_type_id.strip():
                pairs.add((artifact_type_id, sensor_id))
    return pairs


def _collect_atomic_action_ids(src_root: Path) -> set[str]:
    """AST-walk ``src/`` collecting action_id string-literal values from
    every ``@atomic_action(action_id=...)`` decoration.

    Skips files that cannot be parsed or read — a single broken file must
    not crash the audit. Skips decorations whose ``action_id`` is not a
    string literal (e.g. computed) — those cases are too rare in practice
    to silently grant backing credit; they appear as phantoms and the
    finding's resolution prompt clarifies the path forward.
    """
    found: set[str] = set()
    if not src_root.is_dir():
        return found
    for py in src_root.rglob("*.py"):
        try:
            source = py.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("taxonomy_gate: cannot read %s: %s", py, exc)
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.debug("taxonomy_gate: cannot parse %s: %s", py, exc)
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                action_id = _extract_action_id(dec)
                if action_id is not None:
                    found.add(action_id)
    return found


def _extract_action_id(decorator: ast.expr) -> str | None:
    """Return the ``action_id`` keyword value if ``decorator`` is a call to
    ``atomic_action`` with a string-literal ``action_id`` kwarg; else None.

    Accepts both bare (``@atomic_action(...)``) and attribute access
    (``@module.atomic_action(...)``) forms so the check tracks the decoration
    irrespective of import style.
    """
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return None
    if name != "atomic_action":
        return None
    for kw in decorator.keywords:
        if kw.arg != "action_id":
            continue
        value = kw.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        return None
    return None


def _collect_self_resolve_call_sites(src_root: Path) -> dict[str, set[Path]]:
    """AST-walk src/ collecting post_finding(..., resolution_mechanism='self_resolve')
    call sites; for each, trace the subject prefix and map it to the emitting
    module path.

    Subject prefix tracing supports the patterns the surviving five sites use:

    - ``subject = f"{_CONST}::{...}"`` then
      ``post_finding(subject=subject, ...)`` →
      prefix = ``module_constants[_CONST]`` split on ``::``.
    - ``post_finding(subject=f"{_CONST}::{...}", ...)`` → same.
    - ``post_finding(subject="literal::id", ...)`` → prefix = ``"literal"``.

    Skips files that cannot be read or parsed (a single broken file must
    not crash the audit cycle — log and skip). Skips calls whose subject
    cannot be traced — those are too rare in the surviving tree to silently
    grant backing credit; if they arise, the call site's prefix will not
    appear in the site map and the rule will not flag it. Future hardening
    can promote untraceable sites to their own finding class.
    """
    site_map: dict[str, set[Path]] = {}
    if not src_root.is_dir():
        return site_map
    for py in src_root.rglob("*.py"):
        try:
            source = py.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("taxonomy_gate: cannot read %s: %s", py, exc)
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            logger.debug("taxonomy_gate: cannot parse %s: %s", py, exc)
            continue

        module_constants = _collect_module_string_constants(tree)

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            subject_assigns = _collect_subject_assignments_by_lineno(fn)
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                if not _is_post_finding_self_resolve_call(node):
                    continue
                prefix = _extract_subject_prefix(
                    node, subject_assigns, module_constants
                )
                if prefix is None:
                    continue
                site_map.setdefault(prefix, set()).add(py)
    return site_map


def _collect_module_string_constants(tree: ast.AST) -> dict[str, str]:
    """Return ``{name: value}`` for every module-level
    ``NAME = "string literal"`` assignment. Used to resolve subject-prefix
    constants referenced from inside f-strings at post_finding call sites.
    """
    constants: dict[str, str] = {}
    if not isinstance(tree, ast.Module):
        return constants
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(
            node.value.value, str
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = node.value.value
    return constants


def _collect_subject_assignments_by_lineno(
    fn: ast.AST,
) -> list[tuple[int, ast.expr]]:
    """Return ``[(lineno, value), ...]`` for every ``subject = <expr>``
    assignment in the function body, sorted by lineno.

    A flat "name → last value" dict would lose the per-call-site binding
    when ``subject`` is rebound multiple times within the same function
    (e.g., proposal_pipeline_shop_manager's three sequential for-loops,
    each rebinding ``subject = f"{_CONST_n}::{id}"`` before calling
    ``post_finding``). Returning the lineno-ordered list lets the caller
    pick the closest preceding assignment for each call site, which is
    the right binding under straight-line code. Conditional flow (if/else
    branches that both write ``subject``) is rare in the surviving tree
    and not worth tracing here; the engine would over-attribute to the
    later branch, which the rule statement's "any emitter" generosity
    absorbs.
    """
    assigns: list[tuple[int, ast.expr]] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "subject":
                assigns.append((node.lineno, node.value))
    assigns.sort()
    return assigns


def _is_post_finding_self_resolve_call(call: ast.Call) -> bool:
    """True iff ``call`` invokes ``post_finding`` (bare or attribute access)
    with a keyword argument ``resolution_mechanism="self_resolve"`` whose
    value is a string literal. Tracks only literal-string classifications;
    dynamically-computed mechanism values are too rare to warrant tracing
    here and would also bypass the closed-vocabulary-at-call-site discipline
    Revision B (b) imposes.
    """
    func = call.func
    if isinstance(func, ast.Attribute):
        method_name = func.attr
    elif isinstance(func, ast.Name):
        method_name = func.id
    else:
        return False
    if method_name != "post_finding":
        return False
    for kw in call.keywords:
        if kw.arg != "resolution_mechanism":
            continue
        if isinstance(kw.value, ast.Constant) and kw.value.value == "self_resolve":
            return True
    return False


def _extract_subject_prefix(
    call: ast.Call,
    subject_assigns: list[tuple[int, ast.expr]],
    module_constants: dict[str, str],
) -> str | None:
    """Trace ``post_finding(subject=…)``'s subject expression to its prefix.

    Returns the module-level constant value (split on ``::``) when the
    expression is an f-string with a Name reference, or the literal prefix
    before ``::`` when the expression is a string constant. Returns None
    when the chain cannot be resolved (e.g., the subject is built from a
    function-argument variable or a runtime computation).

    When ``subject=`` is the local-variable Name ``subject``, the binding
    is resolved by picking the closest preceding ``subject = <expr>``
    assignment in ``subject_assigns`` (lineno < call.lineno; max lineno
    wins). This handles the proposal_pipeline_shop_manager pattern where
    three sequential for-loops each rebind ``subject`` before calling
    ``post_finding``, producing three distinct prefixes.
    """
    subject_expr: ast.expr | None = None
    for kw in call.keywords:
        if kw.arg == "subject":
            subject_expr = kw.value
            break
    if subject_expr is None:
        return None
    if isinstance(subject_expr, ast.Name) and subject_expr.id == "subject":
        call_lineno = getattr(call, "lineno", 0)
        binding: ast.expr | None = None
        for lineno, value in subject_assigns:
            if lineno < call_lineno:
                binding = value
            else:
                break
        if binding is None:
            return None
        return _prefix_from_expr(binding, module_constants)
    return _prefix_from_expr(subject_expr, module_constants)


def _prefix_from_expr(expr: ast.expr, module_constants: dict[str, str]) -> str | None:
    """Extract a subject prefix from an f-string or constant expression.

    Supported shapes:

    - ``f"{NAME}::{...}"`` → ``module_constants[NAME]`` split on ``::``.
    - ``f"literal::{...}"`` → ``"literal"``.
    - ``"literal::id"`` → ``"literal"``.

    Concatenation (``a + b``) and other dynamic constructions return None.
    """
    if isinstance(expr, ast.JoinedStr):
        if not expr.values:
            return None
        first = expr.values[0]
        if isinstance(first, ast.FormattedValue) and isinstance(first.value, ast.Name):
            const_value = module_constants.get(first.value.id)
            if const_value is None:
                return None
            return const_value.split("::", 1)[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value.split("::", 1)[0]
        return None
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value.split("::", 1)[0]
    return None


def _module_docstring_has_canonical_block(module_path: Path) -> bool:
    """True iff ``module_path``'s top-level docstring (the first string
    literal at the module body's head) contains the canonical
    ``ADR-091 D2 Revision B resolution classification:`` block. Read-only;
    parse failures and IO errors return False (treated as missing).
    """
    try:
        source = module_path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    docstring = ast.get_docstring(tree)
    if docstring is None:
        return False
    return _RESOLVER_DOCSTRING_BLOCK in docstring


def _prefix_appears_in_tests(prefix: str, tests_root: Path) -> bool:
    """True iff ``prefix`` appears anywhere in any ``*.py`` source file
    under ``tests_root``. Generous signal per Revision B (h)'s scope-
    decision tolerance: a test referencing the prefix as a string (in an
    assertion, fixture, or seed value) is taken to exercise resolver
    ownership for that prefix.

    Substring match against file source is intentionally simple — parsing
    test bodies for transition assertions would be brittle and would false-
    positive on legitimate posting-only tests like
    ``tests/will/workers/test_resolution_mechanism_classification.py``,
    which is the exemption shape Revision B (h) explicitly permits.
    """
    if not tests_root.is_dir():
        return False
    for py in tests_root.rglob("*.py"):
        try:
            source = py.read_text(encoding="utf-8")
        except OSError:
            continue
        if prefix in source:
            return True
    return False
