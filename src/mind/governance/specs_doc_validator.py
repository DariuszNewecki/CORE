# src/mind/governance/specs_doc_validator.py
"""
.specs/ document-header structural validator (ADR-105 D6, hook 1).

Sibling of meta_validator: where MetaValidator validates .intent/ documents
against the GLOBAL meta-schema, SpecsDocValidator validates the YAML frontmatter
header of each modeled .specs/ document (adr, paper, …) against the per-class
header schema declared via that artifact type's `schema_ref`.

This is STRUCTURAL conformance (does the header match its schema), deliberately
distinct from the CCC's COHERENCE checks (cross-document relationships) — ADR-105
keeps the two natures in separate homes. The modeled-class set is DERIVED from the
artifact_type registry (every .specs/ type with a non-null schema_ref), never
hardcoded, per architecture.artifact_discovery_through_registry.

Cross-tree $ref: the per-class schemas live under .specs/META/ but reference the
shared enum vocabulary in .intent/META/enums.json. The registry retrieve callback
resolves any `enums.json` reference to that canonical file — mirroring
meta_validator's filename-fallback resolution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from referencing.jsonschema import DRAFT7

from mind.governance.meta_validator import ValidationError, ValidationReport
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)

# Leading YAML frontmatter: optional BOM/whitespace, an optional single HTML
# comment (the `<!-- path: … -->` convention some docs carry), then a --- … ---
# block at the top of the document.
_FRONTMATTER_RE = re.compile(
    r"\A﻿?\s*(?:<!--.*?-->\s*)?---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)",
    re.DOTALL,
)


# ID: 5de36096-ebfe-46be-aab4-e7f7fe4987f5
def parse_frontmatter(text: str) -> dict[str, Any] | None:
    """Extract and parse the leading YAML frontmatter block of a .specs document.

    Returns the parsed mapping, None if the document has no frontmatter block, or
    an empty dict if a block is present but its YAML is malformed or not a mapping
    (so callers can distinguish "absent" from "present but broken").
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        loaded = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# ID: ba6dc6a7-a7de-4d9c-bf53-6ffed21dfd96
class SpecsDocValidator:
    """Validate modeled .specs/ document headers against their per-class schemas."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo = get_intent_repository()
        self._intent_root = self._repo.root
        self._repo_root = Path(repo_root) if repo_root else self._intent_root.parent
        self._enums_path = self._intent_root / "META" / "enums.json"
        self._schema_cache: dict[str, dict[str, Any]] = {}
        self.errors: list[ValidationError] = []
        self.warnings: list[ValidationError] = []

    def _modeled_types(self) -> list[tuple[str, list[str], str]]:
        """Derive (kind_id, discovery_globs, schema_ref) for every .specs/ artifact
        type that declares a header schema. Sourced from the registry, never
        hardcoded — new modeled classes are picked up automatically."""
        out: list[tuple[str, list[str], str]] = []
        for at in self._repo.list_artifact_types():
            content = at.content
            schema_ref = content.get("schema_ref")
            discovery = content.get("discovery") or []
            if not schema_ref:
                continue
            if not any(str(g).startswith(".specs/") for g in discovery):
                continue
            out.append((content["id"], list(discovery), schema_ref))
        return out

    def _load_schema(self, schema_ref: str) -> dict[str, Any]:
        if schema_ref not in self._schema_cache:
            path = self._repo_root / schema_ref
            self._schema_cache[schema_ref] = json.loads(
                path.read_text(encoding="utf-8")
            )
        return self._schema_cache[schema_ref]

    def _build_registry(self) -> Registry:
        enums_path = self._enums_path

        def _retrieve(uri: str) -> Resource:
            name = uri.split("#", 1)[0].rsplit("/", 1)[-1]
            if name == "enums.json" and enums_path.is_file():
                return Resource.from_contents(
                    json.loads(enums_path.read_text(encoding="utf-8")),
                    default_specification=DRAFT7,
                )
            raise NoSuchResource(uri)

        return Registry(retrieve=_retrieve)  # type: ignore[call-arg]

    # ID: 8b2787f8-73fe-4d83-b77e-98fabb52a807
    def validate_header(
        self,
        schema: dict[str, Any],
        header: dict[str, Any],
        *,
        document: str = "<header>",
    ) -> list[ValidationError]:
        """Validate a single frontmatter header mapping against a per-class schema.

        Resolves the schema's cross-tree enum $refs into .intent/META/enums.json.
        """
        errors: list[ValidationError] = []
        registry = self._build_registry()
        try:
            validator = Draft7Validator(schema, registry=registry)
            for e in validator.iter_errors(header):
                path = ".".join(map(str, e.path)) or "root"
                errors.append(
                    ValidationError(
                        document, "schema_violation", e.message, "error", path
                    )
                )
        except Exception as e:  # report any resolver/validator failure, never raise
            errors.append(
                ValidationError(
                    document, "validator_error", f"Internal validator error: {e}"
                )
            )
        return errors

    # ID: ed9efdab-1744-4112-a670-df419306e58f
    def validate_all_documents(self) -> ValidationReport:
        """Validate every modeled .specs/ document's frontmatter header."""
        self.errors.clear()
        self.warnings.clear()
        checked = valid = invalid = 0

        for kind, globs, schema_ref in self._modeled_types():
            try:
                schema = self._load_schema(schema_ref)
            except Exception as e:
                self.errors.append(
                    ValidationError(schema_ref, "schema_load_error", str(e))
                )
                continue
            seen: set[Path] = set()
            for glob in globs:
                for path in sorted(self._repo_root.glob(glob)):
                    if path in seen or not path.is_file():
                        continue
                    seen.add(path)
                    rel = str(path.relative_to(self._repo_root))
                    checked += 1
                    header = parse_frontmatter(
                        path.read_text(encoding="utf-8", errors="replace")
                    )
                    if header is None:
                        self.errors.append(
                            ValidationError(
                                rel,
                                "missing_header",
                                f"No YAML frontmatter header (kind={kind})",
                            )
                        )
                        invalid += 1
                        continue
                    errs = self.validate_header(schema, header, document=rel)
                    if errs:
                        self.errors.extend(errs)
                        invalid += 1
                    else:
                        valid += 1

        return ValidationReport(
            valid=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            documents_checked=checked,
            documents_valid=valid,
            documents_invalid=invalid,
        )
