# src/shared/infrastructure/vector/adapters/constitutional_adapter.py

"""
Constitutional Adapter - Policies & Patterns Vectorization

Translates YAML-based constitutional documents (standards, constitution) into
VectorizableItems for the unified VectorIndexService.

This adapter replaces:
- PolicyVectorizer (will/tools/policy_vectorizer.py)
- PatternVectorizer (features/introspection/pattern_vectorizer.py)

Constitutional Alignment: dry_by_design, separation_of_concerns
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.logger import getLogger
from shared.models.vector_models import VectorizableItem
from shared.utils.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


# ID: a47c1cf1-c2cb-4895-8409-ad4e7eede118
class ConstitutionalAdapter:
    """
    Adapts constitutional YAML files into vectorizable items.

    Handles both policies (standards) and patterns using the same chunking logic,
    since they share the same YAML structure and semantic purpose.
    Updated for Charter v3.0.0 structure (Constitution + Standards).
    """

    def __init__(self, source_dir: Path | None = None):
        """
        Initialize the adapter.

        Args:
            source_dir: Directory containing YAML files (defaults to charter dir)
        """
        self.source_dir = source_dir or (settings.REPO_PATH / ".intent" / "charter")
        logger.debug(f"ConstitutionalAdapter initialized for {self.source_dir}")

    # ID: a221eead-aa6f-454e-8b73-1ece7c8a157b
    def policies_to_items(self) -> list[VectorizableItem]:
        """
        Convert all Standards (Architecture, Operations, Code, Data) to vector items.
        Recursively scans .intent/charter/standards/

        Returns:
            List of VectorizableItems for all standard chunks
        """
        # Map legacy 'policies' concept to the new 'standards' directory
        standards_dir = self.source_dir / "standards"
        # Recursively scan because standards are categorized in subdirs
        return self._process_yaml_directory(
            standards_dir, doc_type="standard", recursive=True
        )

    # ID: fd7f2d97-d691-4f5f-b46e-90ce112b6588
    def patterns_to_items(self) -> list[VectorizableItem]:
        """
        Specifically target Architectural Standards as 'patterns' for backward compatibility.

        Returns:
            List of VectorizableItems for all pattern chunks
        """
        # Patterns are now located in standards/architecture/
        arch_dir = self.source_dir / "standards" / "architecture"
        return self._process_yaml_directory(
            arch_dir, doc_type="pattern", recursive=False
        )

    def _process_yaml_directory(
        self, directory: Path, doc_type: str, recursive: bool = False
    ) -> list[VectorizableItem]:
        """
        Process all YAML files in a directory.

        Args:
            directory: Directory containing YAML files
            doc_type: Type of document ("policy", "standard", or "pattern")
            recursive: Whether to scan subdirectories

        Returns:
            List of VectorizableItems from all files
        """
        if not directory.exists():
            # Fail-safe default: log warning and return empty list instead of crashing
            logger.warning("Directory not found: %s", directory)
            return []

        pattern = "**/*.yaml" if recursive else "*.yaml"
        yaml_files = list(directory.glob(pattern))

        # FIXED: Added 'f' prefix for correct formatting
        logger.info("Processing {len(yaml_files)} {doc_type} files from %s", directory)

        all_items: list[VectorizableItem] = []

        for yaml_file in yaml_files:
            try:
                items = self._file_to_items(yaml_file, doc_type)
                all_items.extend(items)
                logger.debug(f"✓ {yaml_file.name}: {len(items)} chunks")
            except Exception as e:
                logger.error("✗ Failed to process {yaml_file.name}: %s", e)

        # FIXED: Added 'f' prefix for correct formatting
        logger.info("Generated {len(all_items)} items from %s files", doc_type)
        return all_items

    def _file_to_items(self, yaml_file: Path, doc_type: str) -> list[VectorizableItem]:
        """
        Convert a single YAML file into vectorizable items.

        Args:
            yaml_file: Path to YAML file
            doc_type: Type of document ("policy" or "pattern")

        Returns:
            List of VectorizableItems for this file
        """
        # Load YAML
        data = strict_yaml_processor.load(yaml_file)

        # Extract document metadata
        doc_id = data.get("id", yaml_file.stem)
        doc_version = data.get("version", "unknown")
        doc_title = data.get("title", doc_id)

        # Chunk the document
        chunks = self._chunk_document(data, doc_id, doc_type)

        # Convert chunks to VectorizableItems
        items = []
        for idx, chunk in enumerate(chunks):
            item_id = f"{doc_id}_{chunk['section_type']}_{idx}"
            content = chunk["content"].strip()

            # CALCULATE HASH for deduplication
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            payload = {
                "doc_id": doc_id,
                "doc_version": doc_version,
                "doc_title": doc_title,
                "doc_type": doc_type,
                "filename": yaml_file.name,
                "section_type": chunk["section_type"],
                "section_path": chunk["section_path"],
                "severity": chunk.get("severity", "error"),
                "content_sha256": content_hash,
            }

            items.append(
                VectorizableItem(
                    item_id=item_id,
                    text=content,
                    payload=payload,
                )
            )

        return items

    def _chunk_document(
        self, data: dict, doc_id: str, doc_type: str
    ) -> list[dict[str, Any]]:
        """
        Chunk a document into semantic sections.

        Strategy: Each meaningful section becomes a chunk for semantic search.

        Args:
            data: Parsed YAML data
            doc_id: Document identifier
            doc_type: Type of document

        Returns:
            List of chunk dictionaries
        """
        chunks: list[dict[str, Any]] = []

        # Universal chunking: title + purpose
        if "title" in data and "purpose" in data:
            chunks.append(
                {
                    "section_type": "purpose",
                    "section_path": "purpose",
                    "content": f"{data['title']}\n\n{data['purpose']}",
                }
            )

        # Pattern-specific: philosophy
        if "philosophy" in data:
            chunks.append(
                {
                    "section_type": "philosophy",
                    "section_path": "philosophy",
                    "content": data["philosophy"],
                }
            )

        # Pattern-specific: requirements
        if "requirements" in data and isinstance(data["requirements"], dict):
            for req_name, req_data in data["requirements"].items():
                if isinstance(req_data, dict) and "mandate" in req_data:
                    content = f"{req_data['mandate']}\n\n"
                    if "implementation" in req_data:
                        impl = req_data["implementation"]
                        if isinstance(impl, list):
                            content += "Implementation:\n" + "\n".join(
                                f"- {item}" for item in impl
                            )
                        else:
                            content += f"Implementation: {impl}"

                    chunks.append(
                        {
                            "section_type": "requirement",
                            "section_path": f"requirements.{req_name}",
                            "content": content,
                            "severity": "error",
                        }
                    )

        # Policy-specific: rules
        if "rules" in data and isinstance(data["rules"], list):
            for rule in data["rules"]:
                if isinstance(rule, dict) and "statement" in rule:
                    content = f"Rule: {rule.get('id', 'unknown')}\n"
                    content += f"Statement: {rule['statement']}\n"
                    content += f"Enforcement: {rule.get('enforcement', 'error')}"

                    chunks.append(
                        {
                            "section_type": "rule",
                            "section_path": f"rules.{rule.get('id', 'unknown')}",
                            "content": content,
                            "severity": rule.get("enforcement", "error"),
                        }
                    )

        # Pattern-specific: validation rules
        if "validation_rules" in data and isinstance(data["validation_rules"], list):
            for rule in data["validation_rules"]:
                if isinstance(rule, dict) and "rule" in rule:
                    content = f"Rule: {rule['rule']}\n"
                    content += f"Description: {rule.get('description', '')}\n"
                    content += f"Severity: {rule.get('severity', 'error')}\n"
                    content += f"Enforcement: {rule.get('enforcement', 'runtime')}"

                    chunks.append(
                        {
                            "section_type": "validation_rule",
                            "section_path": f"validation_rules.{rule['rule']}",
                            "content": content,
                            "severity": rule.get("severity", "error"),
                        }
                    )

        # Pattern-specific: examples
        if "examples" in data and isinstance(data["examples"], dict):
            for example_name, example_data in data["examples"].items():
                if isinstance(example_data, dict):
                    content = f"Example: {example_name}\n"
                    content += strict_yaml_processor.dump_yaml(example_data)

                    chunks.append(
                        {
                            "section_type": "example",
                            "section_path": f"examples.{example_name}",
                            "content": content,
                        }
                    )

        return chunks
