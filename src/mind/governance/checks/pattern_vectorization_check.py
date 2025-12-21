# src/mind/governance/checks/pattern_vectorization_check.py
"""
Pattern Vectorization Governance Check

Enforces pattern vectorization operational rules declared in:
- .intent/.../standard_operations_pattern_vectorization.(yaml|yml|json)
  (policy key: "pattern_vectorization")

Targets:
- pattern_vectorization.chunking.semantic_section.required
- pattern_vectorization.collection.core_patterns.contract
- pattern_vectorization.constitutional_audit.integration_required
- pattern_vectorization.override_policy.disallowed
- pattern_vectorization.pattern_understanding.required
- pattern_vectorization.semantic_validation.required
- pattern_vectorization.update_policy.on_file_change

Design constraints:
- Prefer CORE conventions and internal path resolution.
- Evidence-backed only; fail if discovery is not possible.
- Read-only check: never writes to repo or DB.
- Conservative static verification (text scan + minimal AST hints).
"""

from __future__ import annotations

import fnmatch
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

RULE_CHUNKING_SEMANTIC_SECTION = (
    "pattern_vectorization.chunking.semantic_section.required"
)
RULE_COLLECTION_CORE_PATTERNS = (
    "pattern_vectorization.collection.core_patterns.contract"
)
RULE_CONSTITUTIONAL_AUDIT_INTEGRATION = (
    "pattern_vectorization.constitutional_audit.integration_required"
)
RULE_OVERRIDE_POLICY_DISALLOWED = "pattern_vectorization.override_policy.disallowed"
RULE_PATTERN_UNDERSTANDING_REQUIRED = (
    "pattern_vectorization.pattern_understanding.required"
)
RULE_SEMANTIC_VALIDATION_REQUIRED = "pattern_vectorization.semantic_validation.required"
RULE_UPDATE_POLICY_ON_FILE_CHANGE = "pattern_vectorization.update_policy.on_file_change"

# Conservative discovery keywords (we scan only plausible vectorization/pattern modules)
_DISCOVERY_HINTS = (
    "pattern",
    "patterns",
    "vector",
    "vectorization",
    "qdrant",
    "embedding",
    "constitutional",
    "constitution",
    "audit",
    "chunk",
    "section",
)

# Evidence tokens per rule (policy can override/extend)
_TOKENS_CHUNKING_SEMANTIC_SECTION = (
    "semantic_section",
    "semantic sections",
    "section_header",
    "section header",
    "section boundary",
    "heading",
    "h1",
    "h2",
    "markdown",
    "split_by_section",
    "split_by_heading",
)

_TOKENS_COLLECTION_CORE_PATTERNS = (
    "core_patterns",
    "core-patterns",
    "collection_core_patterns",
    "CORE_PATTERNS",
    "collection_name",
    "collection=",
    "patterns_collection",
)

_TOKENS_CONSTITUTIONAL_AUDIT_INTEGRATION = (
    "constitutional_audit",
    "constitution_audit",
    "audit_constitution",
    "governance audit",
    "rule_enforcement",
    "policy_check",
    "governance.check",
)

_TOKENS_OVERRIDE_POLICY_DISALLOWED = (
    "override_policy",
    "policy_override",
    "bypass_policy",
    "skip_policy",
    "disable_policy",
    "ignore_policy",
)

_TOKENS_PATTERN_UNDERSTANDING_REQUIRED = (
    "pattern_understanding",
    "understand_pattern",
    "pattern_summary",
    "pattern intent",
    "pattern meaning",
    "explain pattern",
    "rationale",
)

_TOKENS_SEMANTIC_VALIDATION_REQUIRED = (
    "semantic_validation",
    "validate_semantic",
    "semantic check",
    "meaningful",
    "coherence",
    "invariant",
    "contract validation",
)

_TOKENS_UPDATE_POLICY_ON_FILE_CHANGE = (
    "on_file_change",
    "file_change",
    "watchdog",
    "file watcher",
    "invalidate_cache",
    "reindex",
    "re-vector",
    "refresh",
    "debounce",
)


@dataclass(frozen=True)
class _Hit:
    file: str
    line: int
    kind: str
    snippet: str


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.
    Filter kwargs to supported parameters to prevent runtime TypeError.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


# ID: b511e515-280a-4cde-843b-03f53222a644
class PatternVectorizationEnforcement(EnforcementMethod):
    """
    Conservative, evidence-backed enforcement for pattern vectorization rules.

    Evidence model:
    - Static source inspection (token hits with file:line snippets).
    - No runtime execution.
    - If relevant code cannot be discovered, fail (ERROR) rather than pass.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: b9236dff-c1d5-41d9-89fa-5d2102d65614
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        include_roots = self._get_str_list(rule_data, "include_roots") or ["src"]
        exclude_globs = self._get_str_list(rule_data, "exclude_globs") or [
            "**/tests/**",
            "**/.venv/**",
            "**/.tox/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/__pycache__/**",
        ]
        evidence_min = self._get_int(rule_data, "evidence_minimum_per_rule", default=1)

        # Optional: policy may add/override tokens
        tokens = self._rule_tokens(self.rule_id, rule_data)
        tokens = [t for t in tokens if str(t).strip()]
        token_set = {t.lower() for t in tokens}

        files = self._collect_files(repo_path, include_roots, exclude_globs)
        if not files:
            return [
                _create_finding_safe(
                    self,
                    message="No source files discovered; cannot validate pattern_vectorization.* rules.",
                    file_path=";".join(include_roots),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                    },
                )
            ]

        candidate_files = self._discover_candidate_files(repo_path, files)
        if not candidate_files:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "No pattern/vectorization-related modules discovered; cannot validate "
                        "pattern_vectorization.* rules."
                    ),
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "files_scanned": len(files),
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                        "discovery_hints": list(_DISCOVERY_HINTS),
                        "hint": "Expected modules mentioning patterns/vectorization/qdrant/chunking/constitutional audit.",
                    },
                )
            ]

        hits: list[_Hit] = []
        parse_errors: list[dict[str, Any]] = []

        # Special: override-policy rule is inverted: evidence is *absence* of bypass tokens in candidate area.
        inverted_absence_rule = self.rule_id == RULE_OVERRIDE_POLICY_DISALLOWED

        for p in candidate_files:
            relp = _rel(repo_path, p)
            try:
                src = p.read_text(encoding="utf-8")
            except Exception as exc:
                parse_errors.append({"file": relp, "error": f"read_failed: {exc}"})
                continue

            # For inverted rule we still scan and treat hits as violations (evidence of non-compliance).
            for i, line in enumerate(src.splitlines(), start=1):
                lowered = line.lower()
                if any(tok in lowered for tok in token_set):
                    hits.append(
                        _Hit(
                            file=relp,
                            line=i,
                            kind="token",
                            snippet=line.strip()[:240],
                        )
                    )

        if inverted_absence_rule:
            # Pass if we found NO bypass/override tokens in the candidate vectorization area.
            ok = len(hits) < evidence_min  # typically evidence_min=1
            if ok:
                return [
                    _create_finding_safe(
                        self,
                        message="No evidence of policy override/bypass detected in pattern vectorization modules.",
                        file_path="src",
                        severity=AuditSeverity.INFO,
                        evidence={
                            "rule_id": self.rule_id,
                            "candidate_files_scanned": len(candidate_files),
                            "tokens_scanned": tokens,
                            "parse_errors_count": len(parse_errors),
                            "parse_errors": parse_errors[:25],
                        },
                    )
                ]
            return [
                _create_finding_safe(
                    self,
                    message="Policy override/bypass indicators detected in pattern vectorization modules (disallowed).",
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "rule_id": self.rule_id,
                        "candidate_files_scanned": len(candidate_files),
                        "tokens_scanned": tokens,
                        "hits_count": len(hits),
                        "hits": [
                            {"file": h.file, "line": h.line, "snippet": h.snippet}
                            for h in hits[:200]
                        ],
                        "parse_errors_count": len(parse_errors),
                        "parse_errors": parse_errors[:25],
                    },
                )
            ]

        # Normal rule: pass if we found at least evidence_min hits.
        ok = len(hits) >= evidence_min
        return [
            _create_finding_safe(
                self,
                message=(
                    f"Evidence found for {self.rule_id}."
                    if ok
                    else f"No evidence found for {self.rule_id}."
                ),
                file_path="src",
                severity=AuditSeverity.INFO if ok else AuditSeverity.ERROR,
                evidence={
                    "rule_id": self.rule_id,
                    "evidence_minimum": evidence_min,
                    "candidate_files_scanned": len(candidate_files),
                    "tokens_scanned": tokens,
                    "hits_count": len(hits),
                    "hits": [
                        {"file": h.file, "line": h.line, "snippet": h.snippet}
                        for h in hits[:200]
                    ],
                    "parse_errors_count": len(parse_errors),
                    "parse_errors": parse_errors[:25],
                    "hint": self._hint_for_rule(self.rule_id),
                },
            )
        ]

    def _rule_tokens(self, rule_id: str, rule_data: dict[str, Any]) -> list[str]:
        # Allow per-rule token overrides in policy: tokens.<rule_id>: [...]
        tokens_override = None
        tokens_section = rule_data.get("tokens")
        if isinstance(tokens_section, dict):
            tokens_override = tokens_section.get(rule_id)

        if isinstance(tokens_override, list):
            base = [str(x) for x in tokens_override]
        elif isinstance(tokens_override, str) and tokens_override.strip():
            base = [tokens_override.strip()]
        else:
            base = list(self._default_tokens(rule_id))

        # Optional global token extensions: tokens_global: [...]
        tokens_global = rule_data.get("tokens_global")
        if isinstance(tokens_global, list):
            base.extend(str(x) for x in tokens_global)
        elif isinstance(tokens_global, str) and tokens_global.strip():
            base.append(tokens_global.strip())

        # Dedup while keeping order
        seen: set[str] = set()
        out: list[str] = []
        for t in base:
            key = t.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def _default_tokens(self, rule_id: str) -> tuple[str, ...]:
        if rule_id == RULE_CHUNKING_SEMANTIC_SECTION:
            return _TOKENS_CHUNKING_SEMANTIC_SECTION
        if rule_id == RULE_COLLECTION_CORE_PATTERNS:
            return _TOKENS_COLLECTION_CORE_PATTERNS
        if rule_id == RULE_CONSTITUTIONAL_AUDIT_INTEGRATION:
            return _TOKENS_CONSTITUTIONAL_AUDIT_INTEGRATION
        if rule_id == RULE_OVERRIDE_POLICY_DISALLOWED:
            return _TOKENS_OVERRIDE_POLICY_DISALLOWED
        if rule_id == RULE_PATTERN_UNDERSTANDING_REQUIRED:
            return _TOKENS_PATTERN_UNDERSTANDING_REQUIRED
        if rule_id == RULE_SEMANTIC_VALIDATION_REQUIRED:
            return _TOKENS_SEMANTIC_VALIDATION_REQUIRED
        if rule_id == RULE_UPDATE_POLICY_ON_FILE_CHANGE:
            return _TOKENS_UPDATE_POLICY_ON_FILE_CHANGE
        return ()

    def _hint_for_rule(self, rule_id: str) -> str:
        if rule_id == RULE_CHUNKING_SEMANTIC_SECTION:
            return "Expected explicit semantic/section-aware chunking (split by headings/sections, not only fixed-size chunks)."
        if rule_id == RULE_COLLECTION_CORE_PATTERNS:
            return "Expected explicit use/definition of the core_patterns collection and a clear contract around it."
        if rule_id == RULE_CONSTITUTIONAL_AUDIT_INTEGRATION:
            return "Expected vectorization pipeline to integrate with constitutional/governance audit (or enforcement hooks)."
        if rule_id == RULE_PATTERN_UNDERSTANDING_REQUIRED:
            return "Expected explicit representation of pattern meaning/rationale/summary alongside vectorization."
        if rule_id == RULE_SEMANTIC_VALIDATION_REQUIRED:
            return "Expected semantic validation step: checking coherence/contract/invariants for extracted patterns."
        if rule_id == RULE_UPDATE_POLICY_ON_FILE_CHANGE:
            return "Expected explicit file-change driven refresh/reindex/update behavior for patterns."
        if rule_id == RULE_OVERRIDE_POLICY_DISALLOWED:
            return "Expected no bypass/override indicators for governance policies in vectorization codepaths."
        return ""

    def _collect_files(
        self,
        repo_path: Path,
        include_roots: list[str],
        exclude_globs: list[str],
    ) -> list[Path]:
        out: list[Path] = []
        for root in include_roots:
            base = repo_path / root
            if not base.exists():
                continue
            for p in base.rglob("*.py"):
                if not p.is_file():
                    continue
                relp = _rel(repo_path, p).replace("\\", "/")
                if any(fnmatch.fnmatch(relp, g) for g in exclude_globs):
                    continue
                out.append(p)
        return sorted(out)

    def _discover_candidate_files(
        self, repo_path: Path, files: list[Path]
    ) -> list[Path]:
        """
        Conservative discovery: select files that are very likely to be involved
        in pattern vectorization (by path + content hints).
        """
        candidates: list[Path] = []
        for p in files:
            relp = _rel(repo_path, p).replace("\\", "/").lower()
            # Path hints
            if any(
                x in relp
                for x in ("pattern", "vector", "qdrant", "embedding", "constitution")
            ):
                candidates.append(p)
                continue

        # If path-based discovery is too broad, keep it but rank.
        # ID: 91735e52-363b-4e70-8e47-a51c129f97da
        def score(p: Path) -> int:
            relp = _rel(repo_path, p).replace("\\", "/").lower()
            s = 0
            for key in (
                "pattern_vector",
                "vectorization",
                "/patterns/",
                "/vector/",
                "qdrant",
                "constitutional",
            ):
                if key in relp:
                    s += 4
            for key in ("chunk", "section", "semantic", "audit", "policy"):
                if key in relp:
                    s += 2
            return s

        ranked = sorted(
            ((score(p), p) for p in candidates), key=lambda x: x[0], reverse=True
        )
        strong = [p for sc, p in ranked if sc >= 2]

        # Hard cap to keep evidence manageable (still deterministic).
        return strong[:250]

    def _get_str_list(self, d: dict[str, Any], key: str) -> list[str]:
        v = d.get(key)
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    def _get_int(self, d: dict[str, Any], key: str, *, default: int) -> int:
        v = d.get(key)
        try:
            if isinstance(v, int):
                return v
            if isinstance(v, str) and re.fullmatch(r"\d+", v.strip()):
                return int(v.strip())
        except Exception:
            return default
        return default


# ID: 6ad9dff1-6d66-4c54-8f3d-9d3b2a8f0d0f
class PatternVectorizationCheck(RuleEnforcementCheck):
    """
    Enforces pattern vectorization standards.

    Ref:
    - standard_operations_pattern_vectorization
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_CHUNKING_SEMANTIC_SECTION,
        RULE_COLLECTION_CORE_PATTERNS,
        RULE_CONSTITUTIONAL_AUDIT_INTEGRATION,
        RULE_OVERRIDE_POLICY_DISALLOWED,
        RULE_PATTERN_UNDERSTANDING_REQUIRED,
        RULE_SEMANTIC_VALIDATION_REQUIRED,
        RULE_UPDATE_POLICY_ON_FILE_CHANGE,
    ]

    # PathResolver policy key expected: "pattern_vectorization"
    policy_file: ClassVar[Path] = settings.paths.policy("pattern_vectorization")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        PatternVectorizationEnforcement(
            rule_id=RULE_CHUNKING_SEMANTIC_SECTION, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_COLLECTION_CORE_PATTERNS, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_CONSTITUTIONAL_AUDIT_INTEGRATION, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_OVERRIDE_POLICY_DISALLOWED, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_PATTERN_UNDERSTANDING_REQUIRED, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_SEMANTIC_VALIDATION_REQUIRED, severity=AuditSeverity.ERROR
        ),
        PatternVectorizationEnforcement(
            rule_id=RULE_UPDATE_POLICY_ON_FILE_CHANGE, severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
