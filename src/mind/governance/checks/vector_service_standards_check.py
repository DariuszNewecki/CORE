# src/mind/governance/checks/vector_service_standards_check.py
"""
Vector Service Standards Governance Check

Targets (standard_architecture_vector_service_standards):
- vector.collection_naming_convention
- vector.deterministic_id_generation
- vector.mandatory_hashing
- vector.bidirectional_sync_integrity
- vector.scroll_pagination
- vector.service_method_usage
- vector.standardized_payloads

Intent
- Ensure CORE's vector layer is deterministic, governable, and SSOT-aligned.
- Evidence-backed checks only. If we cannot discover vector code/config, we fail
  (never “pretend pass”).

Design constraints
- Prefer CORE internal conventions and utilities.
- Conservative static analysis fallback (AST + text scan) only.
- Read-only check: never write to repo or DB.

Policy-driven knobs (rule_data)
- include_roots, exclude_globs
- collection_name_regex (default: r"^[a-z][a-z0-9_]{2,63}$")
- allowed_hash_functions (default: ["sha256","blake2b","blake2s","md5","xxhash"])
- required_payload_keys (default: ["source_id","content_hash"])
- banned_direct_client_tokens (default: ["QdrantClient","qdrant_client","client.upsert","client.search","client.scroll"])
- pagination_tokens (default: ["scroll","next_page","offset","limit","page_token","cursor","scroll_id"])
- evidence_minimum_per_rule (default: 1)

Notes
- These checks are conservative and static. They verify presence of explicit codepaths
  and contracts, not runtime correctness.
"""

from __future__ import annotations

import ast
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

RULE_COLLECTION_NAMING = "vector.collection_naming_convention"
RULE_DETERMINISTIC_ID = "vector.deterministic_id_generation"
RULE_MANDATORY_HASHING = "vector.mandatory_hashing"
RULE_BIDIRECTIONAL_SYNC = "vector.bidirectional_sync_integrity"
RULE_SCROLL_PAGINATION = "vector.scroll_pagination"
RULE_SERVICE_METHOD_USAGE = "vector.service_method_usage"
RULE_STANDARDIZED_PAYLOADS = "vector.standardized_payloads"

_DEFAULT_COLLECTION_REGEX = r"^[a-z][a-z0-9_]{2,63}$"

_HASH_TOKENS = (
    "sha256",
    "blake2b",
    "blake2s",
    "md5",
    "xxhash",
    "hashlib",
    "fingerprint",
)
_DETERMINISTIC_ID_TOKENS = (
    "uuid5",
    "uuid.uuid5",
    "deterministic_id",
    "stable_id",
    "content_id",
)
_COLLECTION_TOKENS = ("collection", "collection_name", "index_name", "namespace")
_SYNC_TOKENS = (
    "bidirectional",
    "sync_back",
    "upsert_link",
    "link_back",
    "source_id",
    "symbol_id",
    "db_id",
    "external_id",
    "write_back",
    "knowledge_graph",
    "ssot",
)
_DEFAULT_PAGINATION_TOKENS = (
    "scroll",
    "next_page",
    "offset",
    "limit",
    "page_token",
    "cursor",
    "scroll_id",
)
_DEFAULT_BANNED_DIRECT_CLIENT_TOKENS = (
    "QdrantClient",
    "qdrant_client",
    "client.upsert",
    "client.search",
    "client.scroll",
    ".upsert(",
    ".search(",
    ".scroll(",
)
_DEFAULT_VECTOR_ABSTRACTION_TOKENS = (
    "VectorIndexService",
    "VectorService",
    "VectorStore",
    "VectorizableItem",
    "vector_index_service",
    "vector_service",
    "vector_store",
)
_DEFAULT_REQUIRED_PAYLOAD_KEYS = ("source_id", "content_hash")


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


@dataclass(frozen=True)
class _Hit:
    file: str
    line: int
    kind: str
    snippet: str


# ID: c313a66e-dec1-4c0e-93a5-97793408b57e
class VectorServiceStandardsEnforcement(EnforcementMethod):
    """
    Shared evidence harvesting; emits one finding per rule invocation.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: d45fcc24-7777-4737-9102-24c976be713c
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

        collection_name_regex = str(
            rule_data.get("collection_name_regex") or _DEFAULT_COLLECTION_REGEX
        )
        allowed_hash_functions = self._get_str_list(
            rule_data, "allowed_hash_functions"
        ) or [
            "sha256",
            "blake2b",
            "blake2s",
            "md5",
            "xxhash",
        ]
        required_payload_keys = self._get_str_list(
            rule_data, "required_payload_keys"
        ) or list(_DEFAULT_REQUIRED_PAYLOAD_KEYS)
        banned_direct_client_tokens = self._get_str_list(
            rule_data, "banned_direct_client_tokens"
        ) or list(_DEFAULT_BANNED_DIRECT_CLIENT_TOKENS)
        pagination_tokens = self._get_str_list(rule_data, "pagination_tokens") or list(
            _DEFAULT_PAGINATION_TOKENS
        )
        evidence_min = self._get_int(rule_data, "evidence_minimum_per_rule", default=1)

        try:
            collection_re = re.compile(collection_name_regex)
        except Exception:
            collection_re = re.compile(_DEFAULT_COLLECTION_REGEX)
            collection_name_regex = _DEFAULT_COLLECTION_REGEX

        files = self._collect_files(repo_path, include_roots, exclude_globs)
        if not files:
            return [
                _create_finding_safe(
                    self,
                    message="No source files discovered; cannot validate vector service standards.",
                    file_path=";".join(include_roots),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                        "repo_path": str(repo_path),
                    },
                )
            ]

        vector_files = self._prioritize_vector_files(repo_path, files)
        if not vector_files:
            return [
                _create_finding_safe(
                    self,
                    message="No vector-related code discovered; cannot validate vector.* standards (expected vector/qdrant/index service modules).",
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "files_scanned": len(files),
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                        "hint": "Expected directories like src/**/vector/** or src/**/qdrant/**",
                    },
                )
            ]

        parse_errors: list[dict[str, Any]] = []
        hits: dict[str, list[_Hit]] = {
            RULE_COLLECTION_NAMING: [],
            RULE_DETERMINISTIC_ID: [],
            RULE_MANDATORY_HASHING: [],
            RULE_BIDIRECTIONAL_SYNC: [],
            RULE_SCROLL_PAGINATION: [],
            RULE_SERVICE_METHOD_USAGE: [],
            RULE_STANDARDIZED_PAYLOADS: [],
        }

        collection_name_examples: list[str] = []
        payload_key_examples: list[dict[str, Any]] = []
        direct_client_hits: list[_Hit] = []
        abstraction_hits: list[_Hit] = []

        for p in vector_files:
            relp = _rel(repo_path, p)
            try:
                src = p.read_text(encoding="utf-8")
            except Exception as exc:
                parse_errors.append({"file": relp, "error": f"read_failed: {exc}"})
                continue

            # Text-level evidence
            hits[RULE_MANDATORY_HASHING].extend(
                self._scan_text_for_tokens(
                    relp,
                    src,
                    allowed_hash_functions + list(_HASH_TOKENS),
                    kind="hash",
                )
            )
            hits[RULE_DETERMINISTIC_ID].extend(
                self._scan_text_for_tokens(
                    relp,
                    src,
                    list(_DETERMINISTIC_ID_TOKENS),
                    kind="deterministic_id",
                )
            )
            hits[RULE_BIDIRECTIONAL_SYNC].extend(
                self._scan_text_for_tokens(relp, src, list(_SYNC_TOKENS), kind="sync")
            )
            hits[RULE_SCROLL_PAGINATION].extend(
                self._scan_text_for_tokens(
                    relp, src, pagination_tokens, kind="pagination"
                )
            )

            direct_client_hits.extend(
                self._scan_text_for_tokens(
                    relp, src, banned_direct_client_tokens, kind="direct_client"
                )
            )
            abstraction_hits.extend(
                self._scan_text_for_tokens(
                    relp,
                    src,
                    list(_DEFAULT_VECTOR_ABSTRACTION_TOKENS),
                    kind="abstraction",
                )
            )

            # AST-level evidence (collections + payload dict keys)
            try:
                tree = ast.parse(src, filename=str(p))
            except Exception as exc:
                parse_errors.append({"file": relp, "error": f"parse_failed: {exc}"})
                continue

            coll_hits, examples = self._scan_collection_names(relp, tree, collection_re)
            hits[RULE_COLLECTION_NAMING].extend(coll_hits)
            collection_name_examples.extend(examples)

            payload_hits, payload_examples = self._scan_payload_dict_keys(
                relp, tree, required_payload_keys
            )
            hits[RULE_STANDARDIZED_PAYLOADS].extend(payload_hits)
            payload_key_examples.extend(payload_examples)

        # Summarize service_method_usage: allow only if we see abstraction usage OR we see no direct client use.
        # If direct client usage exists and abstraction evidence is absent, fail.
        if direct_client_hits and not abstraction_hits:
            hits[RULE_SERVICE_METHOD_USAGE].extend(direct_client_hits[:200])
        elif abstraction_hits:
            hits[RULE_SERVICE_METHOD_USAGE].extend(abstraction_hits[:200])

        # Summarize standardized_payloads: if we found payload dicts containing required keys -> pass evidence.
        # Otherwise fail and show what payload-like dicts we saw.
        rid = self.rule_id

        # ID: 74f34886-afb4-4f11-bb90-ef209aecbb49
        def ok_for(rule: str) -> bool:
            return len(hits.get(rule, [])) >= evidence_min

        # ID: b315b727-9328-4b18-9b76-c7a520be3be2
        def mk(
            rule: str,
            ok: bool,
            msg_ok: str,
            msg_fail: str,
            extra: dict[str, Any],
        ) -> AuditFinding:
            return _create_finding_safe(
                self,
                message=msg_ok if ok else msg_fail,
                file_path="src",
                severity=AuditSeverity.INFO if ok else AuditSeverity.ERROR,
                evidence={
                    "rule_id": rule,
                    "evidence_minimum": evidence_min,
                    "vector_files_scanned": len(vector_files),
                    "parse_errors_count": len(parse_errors),
                    "parse_errors": parse_errors[:25],
                    "hits_count": len(hits.get(rule, [])),
                    "hits": [
                        {
                            "file": h.file,
                            "line": h.line,
                            "kind": h.kind,
                            "snippet": h.snippet,
                        }
                        for h in (hits.get(rule, [])[:200])
                    ],
                    **extra,
                },
            )

        if rid == RULE_MANDATORY_HASHING:
            ok = ok_for(RULE_MANDATORY_HASHING)
            return [
                mk(
                    RULE_MANDATORY_HASHING,
                    ok,
                    msg_ok="Evidence found for mandatory hashing/fingerprinting in vector indexing pipeline.",
                    msg_fail="No evidence found for mandatory hashing/fingerprinting in vector indexing pipeline.",
                    extra={"allowed_hash_functions": allowed_hash_functions},
                )
            ]

        if rid == RULE_DETERMINISTIC_ID:
            # Accept deterministic ID if we see explicit deterministic tokens OR hashing evidence.
            ok = ok_for(RULE_DETERMINISTIC_ID) or ok_for(RULE_MANDATORY_HASHING)
            return [
                mk(
                    RULE_DETERMINISTIC_ID,
                    ok,
                    msg_ok="Evidence found for deterministic ID generation (hash-based and/or uuid5/stable ID helpers).",
                    msg_fail="No evidence found for deterministic ID generation (expected hash-based IDs, uuid5, or stable ID helper).",
                    extra={
                        "hint": "Look for uuid5 / deterministic_id / stable_id usage near upsert/index operations."
                    },
                )
            ]

        if rid == RULE_COLLECTION_NAMING:
            ok = ok_for(RULE_COLLECTION_NAMING)
            return [
                mk(
                    RULE_COLLECTION_NAMING,
                    ok,
                    msg_ok="Evidence found for collection naming convention enforcement or compliant collection names.",
                    msg_fail="No evidence found for collection naming convention enforcement or compliant collection names.",
                    extra={
                        "collection_name_regex": collection_name_regex,
                        "collection_name_examples": collection_name_examples[:20],
                    },
                )
            ]

        if rid == RULE_BIDIRECTIONAL_SYNC:
            ok = ok_for(RULE_BIDIRECTIONAL_SYNC)
            return [
                mk(
                    RULE_BIDIRECTIONAL_SYNC,
                    ok,
                    msg_ok="Evidence found for bidirectional sync integrity (source IDs in vector payloads and/or write-back/linkage paths).",
                    msg_fail="No evidence found for bidirectional sync integrity (expected explicit linkage/write-back/integration codepaths).",
                    extra={
                        "hint": "Look for storing source_id/symbol_id in payload + persisting vector_id back to SSOT/DB or emitting link events."
                    },
                )
            ]

        if rid == RULE_SCROLL_PAGINATION:
            # Evidence means we found pagination tokens. This is conservative; it indicates the code is at least pagination-aware.
            ok = ok_for(RULE_SCROLL_PAGINATION)
            return [
                mk(
                    RULE_SCROLL_PAGINATION,
                    ok,
                    msg_ok="Evidence found for scroll/pagination handling in vector retrieval paths.",
                    msg_fail="No evidence found for scroll/pagination handling (expected scroll/offset/limit/cursor mechanics in retrieval).",
                    extra={"pagination_tokens": pagination_tokens},
                )
            ]

        if rid == RULE_SERVICE_METHOD_USAGE:
            # Pass if we see abstraction evidence OR no direct client usage.
            ok = bool(abstraction_hits) or not bool(direct_client_hits)
            return [
                mk(
                    RULE_SERVICE_METHOD_USAGE,
                    ok,
                    msg_ok="Evidence found for vector service abstraction usage (or no direct vector client calls detected).",
                    msg_fail="Direct vector client usage detected without evidence of using the standard vector service abstraction.",
                    extra={
                        "direct_client_hits_count": len(direct_client_hits),
                        "abstraction_hits_count": len(abstraction_hits),
                        "banned_direct_client_tokens": banned_direct_client_tokens,
                        "expected_abstractions": list(
                            _DEFAULT_VECTOR_ABSTRACTION_TOKENS
                        ),
                        "hint": "Prefer routing all vector operations via the standard Vector* service to enforce contracts consistently.",
                    },
                )
            ]

        if rid == RULE_STANDARDIZED_PAYLOADS:
            ok = ok_for(RULE_STANDARDIZED_PAYLOADS)
            return [
                mk(
                    RULE_STANDARDIZED_PAYLOADS,
                    ok,
                    msg_ok="Evidence found for standardized payloads (required payload keys present in vector payload dicts).",
                    msg_fail="No evidence found for standardized payloads (required payload keys not observed in payload dicts).",
                    extra={
                        "required_payload_keys": required_payload_keys,
                        "payload_key_examples": payload_key_examples[:25],
                        "hint": "Ensure payloads include stable identifiers (e.g., source_id) and integrity markers (e.g., content_hash).",
                    },
                )
            ]

        return [
            _create_finding_safe(
                self,
                message="VectorServiceStandardsEnforcement invoked with unsupported rule_id.",
                file_path="src",
                severity=AuditSeverity.ERROR,
                evidence={"rule_id": rid},
            )
        ]

    def _scan_text_for_tokens(
        self,
        rel_file: str,
        src: str,
        tokens: list[str],
        *,
        kind: str,
    ) -> list[_Hit]:
        out: list[_Hit] = []
        token_set = {t.lower() for t in tokens if str(t).strip()}
        for i, line in enumerate(src.splitlines(), start=1):
            lowered_line = line.lower()
            if any(tok in lowered_line for tok in token_set):
                out.append(
                    _Hit(
                        file=rel_file,
                        line=i,
                        kind=kind,
                        snippet=line.strip()[:220],
                    )
                )
        return out

    def _scan_collection_names(
        self,
        rel_file: str,
        tree: ast.AST,
        collection_re: re.Pattern[str],
    ) -> tuple[list[_Hit], list[str]]:
        hits: list[_Hit] = []
        examples: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and any(
                        tok in t.id.lower() for tok in _COLLECTION_TOKENS
                    ):
                        if isinstance(node.value, ast.Constant) and isinstance(
                            node.value.value, str
                        ):
                            s = node.value.value
                            examples.append(s)
                            if collection_re.match(s):
                                hits.append(
                                    _Hit(
                                        file=rel_file,
                                        line=node.lineno,
                                        kind="collection_name",
                                        snippet=f"{t.id} = {s!r}",
                                    )
                                )
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg and any(
                        tok in kw.arg.lower() for tok in _COLLECTION_TOKENS
                    ):
                        if isinstance(kw.value, ast.Constant) and isinstance(
                            kw.value.value, str
                        ):
                            s = kw.value.value
                            examples.append(s)
                            if collection_re.match(s):
                                hits.append(
                                    _Hit(
                                        file=rel_file,
                                        line=node.lineno,
                                        kind="collection_kw",
                                        snippet=f"{kw.arg}={s!r}",
                                    )
                                )

        return hits, examples

    def _scan_payload_dict_keys(
        self,
        rel_file: str,
        tree: ast.AST,
        required_keys: list[str],
    ) -> tuple[list[_Hit], list[dict[str, Any]]]:
        """
        Evidence-backed heuristic:
        - Look for dict literals that contain at least the required payload keys.
        - We treat any dict that includes "payload" in the surrounding assignment/call
          as a payload candidate.
        """
        req = {k.strip() for k in required_keys if k.strip()}
        hits: list[_Hit] = []
        examples: list[dict[str, Any]] = []

        # ID: b41cd5b8-79f9-4e0d-a541-674f1cd96ed0
        def dict_keys(n: ast.Dict) -> set[str]:
            out: set[str] = set()
            for k in n.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    out.add(k.value)
            return out

        for node in ast.walk(tree):
            # Case A: payload = {...}
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and "payload" in t.id.lower():
                        if isinstance(node.value, ast.Dict):
                            keys = dict_keys(node.value)
                            examples.append(
                                {
                                    "file": rel_file,
                                    "line": node.lineno,
                                    "keys": sorted(keys)[:50],
                                }
                            )
                            if req.issubset(keys):
                                hits.append(
                                    _Hit(
                                        file=rel_file,
                                        line=node.lineno,
                                        kind="payload_assign",
                                        snippet=f"{t.id} keys={sorted(req)} present",
                                    )
                                )

            # Case B: call(..., payload={...})
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg
                        and "payload" in kw.arg.lower()
                        and isinstance(kw.value, ast.Dict)
                    ):
                        keys = dict_keys(kw.value)
                        examples.append(
                            {
                                "file": rel_file,
                                "line": node.lineno,
                                "keys": sorted(keys)[:50],
                            }
                        )
                        if req.issubset(keys):
                            hits.append(
                                _Hit(
                                    file=rel_file,
                                    line=node.lineno,
                                    kind="payload_kw",
                                    snippet=f"{kw.arg} keys={sorted(req)} present",
                                )
                            )

        return hits, examples

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

    def _prioritize_vector_files(
        self, repo_path: Path, files: list[Path]
    ) -> list[Path]:
        # ID: d76b2c8b-97a2-4018-85bd-aa949f664cdb
        def score(p: Path) -> int:
            relp = _rel(repo_path, p).replace("\\", "/").lower()
            s = 0
            if "/vector/" in relp:
                s += 5
            if "qdrant" in relp:
                s += 5
            if "vector_index" in relp or "vectorindex" in relp:
                s += 4
            if "vector_store" in relp or "vectorstore" in relp:
                s += 4
            if "embed" in relp or "embedding" in relp:
                s += 2
            return s

        ranked = sorted(
            ((score(p), p) for p in files), key=lambda x: x[0], reverse=True
        )
        return [p for sc, p in ranked if sc > 0]

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
            if isinstance(v, str) and v.strip().isdigit():
                return int(v.strip())
        except Exception:
            return default
        return default


# ID: 2f3b3b1c-2e9a-4f2d-8bb0-8a9d6dcb6c6f
class VectorServiceStandardsCheck(RuleEnforcementCheck):
    """
    Enforces vector service standards.

    Ref:
    - standard_architecture_vector_service_standards
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_COLLECTION_NAMING,
        RULE_DETERMINISTIC_ID,
        RULE_MANDATORY_HASHING,
        RULE_BIDIRECTIONAL_SYNC,
        RULE_SCROLL_PAGINATION,
        RULE_SERVICE_METHOD_USAGE,
        RULE_STANDARDIZED_PAYLOADS,
    ]

    policy_file: ClassVar[Path] = settings.paths.policy("vector_service_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        VectorServiceStandardsEnforcement(
            rule_id=RULE_COLLECTION_NAMING, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_DETERMINISTIC_ID, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_MANDATORY_HASHING, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_BIDIRECTIONAL_SYNC, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_SCROLL_PAGINATION, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_SERVICE_METHOD_USAGE, severity=AuditSeverity.ERROR
        ),
        VectorServiceStandardsEnforcement(
            rule_id=RULE_STANDARDIZED_PAYLOADS, severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
