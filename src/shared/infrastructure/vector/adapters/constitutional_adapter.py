# src/shared/infrastructure/vector/adapters/constitutional_adapter.py

"""
Constitutional Adapter - Constitution/Policies/Standards Vectorization

Converts constitutional documents (constitution + policies + optional standards)
into VectorizableItems for VectorIndexService.

Canonical intent layout (SSOT):
    .intent/
      constitution/
      policies/
      schemas/
      standards/   (optional; may be empty depending on rollout)

Design principles:
    - Deterministic path resolution via settings.paths
    - Stable, canonical document keys based on relative path under the intent root
    - Explicit doc_type separation: constitution | policy | standard | pattern
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, ClassVar

from shared.config import settings
from shared.logger import getLogger
from shared.models.vector_models import VectorizableItem
from shared.utils.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


# ID: bd536b63-ab28-435d-bdd6-bdd4d90b33f0
class ConstitutionalAdapter:
    """Adapts constitutional files into vectorizable items."""

    _EXTENSIONS: ClassVar[tuple[str, ...]] = (".json", ".yaml", ".yml")

    def __init__(self, intent_root: Path | None = None):
        """
        Args:
            intent_root: Optional override for .intent root.
                        Defaults to settings.paths.intent_root.
        """
        self.intent_root = (intent_root or settings.paths.intent_root).resolve()
        logger.debug(
            "ConstitutionalAdapter initialized (intent_root=%s)", self.intent_root
        )

    # -------------------------------------------------------------------------
    # Public conversion APIs
    # -------------------------------------------------------------------------

    # ID: 7d7f430c-fd4b-4b99-9e35-76a28b93b492
    def policies_to_items(self) -> list[VectorizableItem]:
        """Convert all executable governance policies into vector items."""
        return self._process_dir(
            self._policies_dir(), doc_type="policy", recursive=True, key_root="policies"
        )

    # ID: 5beb285c-cec2-4d2b-8107-4c948e62d818
    def patterns_to_items(self) -> list[VectorizableItem]:
        """
        Convert architecture patterns into vector items.

        Canonical behavior:
            Treat patterns as a subset of governance policies under policies/architecture.
        """
        arch_dir = self._policies_dir() / "architecture"
        return self._process_dir(
            arch_dir, doc_type="pattern", recursive=False, key_root="policies"
        )

    # ID: a048dee6-165e-4f74-bd20-8dcacf87125f
    def constitution_to_items(self) -> list[VectorizableItem]:
        """Convert constitution documents into vector items."""
        return self._process_dir(
            self._constitution_dir(),
            doc_type="constitution",
            recursive=True,
            key_root="constitution",
        )

    # Optional: keep standards indexing separate and correctly typed
    # ID: 6d5a1ee7-ebc0-44cd-bcaf-b30045d73547
    def standards_to_items(self) -> list[VectorizableItem]:
        """
        Convert standards documents into vector items.

        NOTE:
            Your current canonical tree shows standards/ exists but may be empty.
            This function is safe to call even when empty.
        """
        return self._process_dir(
            self._standards_dir(),
            doc_type="standard",
            recursive=True,
            key_root="standards",
        )

    # Backward compat alias: older callers may still use this name
    # ID: bb43de2b-45e4-4889-aa23-c0bcd965d73d
    def enforcement_policies_to_items(self) -> list[VectorizableItem]:
        """Alias for policies_to_items()."""
        return self.policies_to_items()

    # -------------------------------------------------------------------------
    # Directory resolution (deterministic; no silent semantic drift)
    # -------------------------------------------------------------------------

    def _standards_dir(self) -> Path:
        """Get standards directory (optional)."""
        return (self.intent_root / "standards").resolve()

    def _constitution_dir(self) -> Path:
        """Get constitution directory."""
        return (self.intent_root / "constitution").resolve()

    def _policies_dir(self) -> Path:
        """Get policies directory."""
        return (self.intent_root / "policies").resolve()

    def _require_path(self, attr_name: str, fallback_name: str) -> Path:
        """
        Resolve an intent path deterministically.

        We still provide a fallback for robustness, but we log it as a warning,
        because in CORE the resolver contract should be the SSOT.
        """
        if hasattr(settings, "paths") and hasattr(settings.paths, attr_name):
            value = getattr(settings.paths, attr_name)
            if isinstance(value, Path):
                return value
            if callable(value):
                resolved = value()
                if isinstance(resolved, Path):
                    return resolved

        fallback = (self.intent_root / fallback_name).resolve()
        logger.warning(
            "PathResolver missing '%s'; using fallback path: %s", attr_name, fallback
        )
        return fallback

    # -------------------------------------------------------------------------
    # Processing
    # -------------------------------------------------------------------------

    def _process_dir(
        self,
        directory: Path,
        *,
        doc_type: str,
        recursive: bool = False,
        key_root: str,
    ) -> list[VectorizableItem]:
        """Process directory and convert files to vector items."""
        if not directory.exists():
            logger.warning("Directory not found for %s: %s", doc_type, directory)
            return []

        files = self._collect_files(directory, recursive)
        if not files:
            logger.info("No %s files found under %s", doc_type, directory)
            return []

        logger.info("Processing %s %s file(s) from %s", len(files), doc_type, directory)

        items: list[VectorizableItem] = []
        for file_path in files:
            items.extend(self._process_file(file_path, doc_type, key_root=key_root))

        logger.info("Generated %s item(s) from %s file(s)", len(items), len(files))
        return items

    def _collect_files(self, directory: Path, recursive: bool) -> list[Path]:
        """Collect JSON/YAML files from directory."""
        collected: set[Path] = set()
        for ext in self._EXTENSIONS:
            if recursive:
                collected.update(p for p in directory.rglob(f"*{ext}") if p.is_file())
            else:
                collected.update(p for p in directory.glob(f"*{ext}") if p.is_file())
        return sorted(collected)

    def _process_file(
        self, file_path: Path, doc_type: str, *, key_root: str
    ) -> list[VectorizableItem]:
        """Process a single file and convert to vector items."""
        try:
            data = strict_yaml_processor.load(file_path)
            if not isinstance(data, dict):
                raise ValueError(
                    f"Expected mapping in {file_path}, got {type(data).__name__}"
                )
            return self._data_to_items(data, file_path, doc_type, key_root=key_root)
        except Exception as exc:
            logger.exception("Failed to process %s (%s): %s", file_path, doc_type, exc)
            return []

    def _data_to_items(
        self,
        data: dict[str, Any],
        file_path: Path,
        doc_type: str,
        *,
        key_root: str,
    ) -> list[VectorizableItem]:
        """Convert document data to vector items."""
        # Prefer explicit doc fields if present, but always compute a canonical doc_key.
        doc_id = self._safe_str(data.get("id")) or file_path.stem
        doc_version = self._safe_str(data.get("version")) or "unknown"
        doc_title = self._safe_str(data.get("title")) or doc_id

        doc_key = self._compute_doc_key(file_path, key_root=key_root)

        chunks = self._chunk_document(data)
        items: list[VectorizableItem] = []
        for idx, chunk in enumerate(chunks):
            item = self._chunk_to_item(
                chunk=chunk,
                idx=idx,
                doc_id=doc_id,
                doc_key=doc_key,
                doc_version=doc_version,
                doc_title=doc_title,
                doc_type=doc_type,
                file_path=file_path,
            )
            if item is not None:
                items.append(item)
        return items

    def _compute_doc_key(self, file_path: Path, *, key_root: str) -> str:
        """
        Compute canonical document key based on canonical intent layout.

        key_root must be one of: policies | constitution | standards.
        Returns a stable path-like key without extension, e.g.:
            policies/code/code_standards
            constitution/authority
        """
        root_dir = self.intent_root / key_root
        try:
            rel = file_path.resolve().relative_to(root_dir.resolve())
            rel_no_ext = rel.with_suffix("")
            return f"{key_root}/{rel_no_ext.as_posix()}"
        except Exception:
            # Fallback: still stable-ish, but should not happen in a healthy repo.
            return f"{key_root}/{file_path.stem}"

    def _chunk_to_item(
        self,
        *,
        chunk: dict[str, Any],
        idx: int,
        doc_id: str,
        doc_key: str,
        doc_version: str,
        doc_title: str,
        doc_type: str,
        file_path: Path,
    ) -> VectorizableItem | None:
        """Convert a chunk to a VectorizableItem."""
        content = self._safe_str(chunk.get("content", "")).strip()
        if not content:
            return None

        section_type = self._safe_str(chunk.get("section_type")) or "section"
        section_path = self._safe_str(chunk.get("section_path")) or section_type

        # Make item_id stable and collision-resistant across taxonomy.
        # doc_key already includes policy/constitution/standard prefix and relative path.
        item_id = f"{doc_key}:{section_type}:{idx}"

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        try:
            rel_path = file_path.relative_to(settings.REPO_PATH)
            rel_path_str = str(rel_path).replace("\\", "/")
        except Exception:
            rel_path_str = str(file_path).replace("\\", "/")

        payload = {
            "doc_id": doc_id,
            "doc_key": doc_key,
            "doc_version": doc_version,
            "doc_title": doc_title,
            "doc_type": doc_type,
            "filename": file_path.name,
            "file_path": rel_path_str,
            "section_type": section_type,
            "section_path": section_path,
            "severity": self._safe_str(chunk.get("severity")) or "error",
            "content_sha256": content_hash,
        }
        return VectorizableItem(item_id=item_id, text=content, payload=payload)

    # -------------------------------------------------------------------------
    # Chunking
    # -------------------------------------------------------------------------

    def _chunk_document(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk a document into semantic sections."""
        chunks: list[dict[str, Any]] = []

        title = self._safe_str(data.get("title")).strip()
        purpose = self._safe_str(data.get("purpose")).strip()
        if title and purpose:
            chunks.append(
                {
                    "section_type": "purpose",
                    "section_path": "purpose",
                    "content": f"{title}\n\n{purpose}",
                }
            )

        philosophy = self._safe_str(data.get("philosophy")).strip()
        if philosophy:
            chunks.append(
                {
                    "section_type": "philosophy",
                    "section_path": "philosophy",
                    "content": philosophy,
                }
            )

        requirements = data.get("requirements")
        if isinstance(requirements, dict):
            chunks.extend(self._chunk_requirements(requirements))

        rules = data.get("rules")
        if isinstance(rules, list):
            chunks.extend(self._chunk_rules(rules))

        validation_rules = data.get("validation_rules")
        if isinstance(validation_rules, list):
            chunks.extend(self._chunk_validation_rules(validation_rules))

        examples = data.get("examples")
        if isinstance(examples, dict):
            chunks.extend(self._chunk_examples(examples))

        return chunks

    def _chunk_requirements(self, requirements: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk requirements section."""
        chunks: list[dict[str, Any]] = []
        for req_name, req_data in requirements.items():
            if not isinstance(req_name, str) or not isinstance(req_data, dict):
                continue
            mandate = self._safe_str(req_data.get("mandate")).strip()
            if not mandate:
                continue

            content = f"{mandate}\n"
            impl = req_data.get("implementation")
            if impl is not None:
                content += "\nImplementation:\n"
                if isinstance(impl, list):
                    lines = [self._safe_str(x).strip() for x in impl if x is not None]
                    lines = [x for x in lines if x]
                    content += "\n".join(f"- {x}" for x in lines)
                else:
                    content += self._safe_str(impl).strip()

            chunks.append(
                {
                    "section_type": "requirement",
                    "section_path": f"requirements.{req_name}",
                    "content": content,
                    "severity": "error",
                }
            )
        return chunks

    def _chunk_rules(self, rules: list[Any]) -> list[dict[str, Any]]:
        """Chunk rules section."""
        chunks: list[dict[str, Any]] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            statement = self._safe_str(rule.get("statement")).strip()
            if not statement:
                continue

            rule_id = self._safe_str(rule.get("id")) or "unknown"
            enforcement = self._safe_str(rule.get("enforcement")) or "error"
            content = (
                f"Rule: {rule_id}\nStatement: {statement}\nEnforcement: {enforcement}"
            )
            chunks.append(
                {
                    "section_type": "rule",
                    "section_path": f"rules.{rule_id}",
                    "content": content,
                    "severity": enforcement,
                }
            )
        return chunks

    def _chunk_validation_rules(self, rules: list[Any]) -> list[dict[str, Any]]:
        """Chunk validation rules section."""
        chunks: list[dict[str, Any]] = []
        for rule in rules:
            if not isinstance(rule, dict):
                continue

            rule_name = self._safe_str(rule.get("rule")).strip()
            if not rule_name:
                continue

            description = self._safe_str(rule.get("description")).strip()
            severity = self._safe_str(rule.get("severity")) or "error"
            enforcement = self._safe_str(rule.get("enforcement")) or "runtime"
            content = (
                f"Rule: {rule_name}\n"
                f"Description: {description}\n"
                f"Severity: {severity}\n"
                f"Enforcement: {enforcement}"
            )
            chunks.append(
                {
                    "section_type": "validation_rule",
                    "section_path": f"validation_rules.{rule_name}",
                    "content": content,
                    "severity": severity,
                }
            )
        return chunks

    def _chunk_examples(self, examples: dict[str, Any]) -> list[dict[str, Any]]:
        """Chunk examples section."""
        chunks: list[dict[str, Any]] = []
        for example_name, example_data in examples.items():
            if not isinstance(example_name, str) or not isinstance(example_data, dict):
                continue
            content = (
                f"Example: {example_name}\n"
                f"{strict_yaml_processor.dump_yaml(example_data)}"
            )
            chunks.append(
                {
                    "section_type": "example",
                    "section_path": f"examples.{example_name}",
                    "content": content,
                }
            )
        return chunks

    def _safe_str(self, value: Any) -> str:
        """Safely convert value to string."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)
