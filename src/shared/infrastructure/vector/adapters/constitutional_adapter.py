# src/shared/infrastructure/vector/adapters/constitutional_adapter.py

"""
Constitutional Adapter - Constitution/Policies/Standards Vectorization

Orchestrates transformation of constitutional documents into VectorizableItems
for semantic search.

CONSTITUTIONAL COMPLIANCE:
- Uses IntentRepository as SSOT for all .intent/ access
- NO direct filesystem crawling
- Delegates discovery and loading to IntentRepository
- Pure orchestration: IntentRepository → chunker → item_builder → VectorizableItems

Architecture (Mind-Body-Will):
    Mind (IntentRepository): Knows where files are, loads them
    Body (ConstitutionalAdapter): Orchestrates transformation
    Will (VectorIndexService): Stores vectors for semantic search

Modular Design:
- constitutional/chunker: Document chunking logic
- constitutional/item_builder: VectorizableItem construction
- constitutional/doc_key_resolver: Canonical key computation
- This module: Orchestration only
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from shared.infrastructure.intent.intent_repository import (
    IntentRepository,
    PolicyRef,
    get_intent_repository,
)
from shared.infrastructure.vector.adapters.constitutional.item_builder import (
    data_to_items,
)
from shared.logger import getLogger
from shared.models.vector_models import VectorizableItem


logger = getLogger(__name__)


# ID: bd536b63-ab28-435d-bdd6-bdd4d90b33f0
class ConstitutionalAdapter:
    """
    Adapts constitutional files into vectorizable items.

    CONSTITUTIONAL BOUNDARY:
    - ALL .intent/ access goes through IntentRepository
    - NO direct filesystem operations
    - Pure orchestration: PolicyRef + document data → VectorizableItem
    """

    _EXTENSIONS: ClassVar[tuple[str, ...]] = (".json", ".yaml", ".yml")

    def __init__(self, intent_repository: IntentRepository | None = None):
        """
        Initialize adapter.

        Args:
            intent_repository: Optional IntentRepository instance.
                              If None, uses singleton from get_intent_repository().
        """
        self.intent_repo = intent_repository or get_intent_repository()
        self.intent_repo.initialize()  # Ensure index is built

        logger.debug(
            "ConstitutionalAdapter initialized (intent_root=%s)", self.intent_repo.root
        )

    # -------------------------------------------------------------------------
    # Public conversion APIs
    # -------------------------------------------------------------------------

    # ID: 7d7f430c-fd4b-4b99-9e35-76a28b93b492
    def policies_to_items(self) -> list[VectorizableItem]:
        """
        Convert all executable governance policies into vector items.

        Uses IntentRepository to discover policies from:
        - .intent/policies/
        - .intent/standards/
        - .intent/rules/

        Returns:
            List of VectorizableItem objects ready for indexing
        """
        policy_refs = self.intent_repo.list_policies()
        return self._process_policy_refs(
            policy_refs, doc_type="policy", key_root="policies"
        )

    # ID: 5beb285c-cec2-4d2b-8107-4c948e62d818
    def patterns_to_items(self) -> list[VectorizableItem]:
        """
        Convert architecture patterns into vector items.

        Filters policies for those under */architecture/* paths.

        Returns:
            List of VectorizableItem objects for patterns
        """
        all_refs = self.intent_repo.list_policies()

        # Filter for patterns under architecture subdirectories
        pattern_refs = [
            ref
            for ref in all_refs
            if "/architecture/" in str(ref.path).replace("\\", "/")
        ]

        if not pattern_refs:
            logger.info("No architecture pattern files found")
            return []

        return self._process_policy_refs(
            pattern_refs,
            doc_type="pattern",
            key_root="policies",  # Patterns are policies
        )

    # ID: a048dee6-165e-4f74-bd20-8dcacf87125f
    def constitution_to_items(self) -> list[VectorizableItem]:
        """
        Convert constitution documents into vector items.

        Processes files from .intent/constitution/ directory.

        Returns:
            List of VectorizableItem objects for constitution
        """
        return self._process_constitution_dir()

    # ID: 6d5a1ee7-ebc0-44cd-bcaf-b30045d73547
    def standards_to_items(self) -> list[VectorizableItem]:
        """
        Convert standards documents into vector items.

        NOTE: Standards are already included in policies_to_items()
        since IntentRepository searches ["policies", "standards", "rules"].
        This method exists for backward compatibility and explicit standards querying.

        Returns:
            List of VectorizableItem objects for standards
        """
        all_refs = self.intent_repo.list_policies()

        # Filter for standards only (path starts with standards/)
        standards_refs = [
            ref for ref in all_refs if str(ref.policy_id).startswith("standards/")
        ]

        if not standards_refs:
            logger.info("No standards files found")
            return []

        return self._process_policy_refs(
            standards_refs, doc_type="standard", key_root="standards"
        )

    # ID: bb43de2b-45e4-4889-aa23-c0bcd965d73d
    def enforcement_policies_to_items(self) -> list[VectorizableItem]:
        """Backward compatibility alias for policies_to_items()."""
        return self.policies_to_items()

    # -------------------------------------------------------------------------
    # Processing - Uses IntentRepository data
    # -------------------------------------------------------------------------

    def _process_policy_refs(
        self,
        policy_refs: list[PolicyRef],
        *,
        doc_type: str,
        key_root: str,
    ) -> list[VectorizableItem]:
        """
        Process PolicyRef objects from IntentRepository into VectorizableItems.

        Args:
            policy_refs: List of PolicyRef from IntentRepository
            doc_type: Document type (policy, pattern, standard)
            key_root: Root for key generation (policies, standards)

        Returns:
            List of VectorizableItem objects
        """
        if not policy_refs:
            logger.info("No %s files to process", doc_type)
            return []

        logger.info("Processing %s %s file(s)", len(policy_refs), doc_type)

        items: list[VectorizableItem] = []
        for ref in policy_refs:
            try:
                # Load document through IntentRepository (SSOT)
                data = self.intent_repo.load_document(ref.path)

                if not isinstance(data, dict):
                    logger.warning(
                        "Skipping non-dict document: %s (type=%s)",
                        ref.path,
                        type(data).__name__,
                    )
                    continue

                # Transform to VectorizableItems (delegates to item_builder)
                file_items = data_to_items(
                    data,
                    ref.path,
                    doc_type,
                    key_root=key_root,
                    intent_root=self.intent_repo.root,
                )
                items.extend(file_items)

            except Exception as exc:
                logger.exception(
                    "Failed to process %s (%s): %s", ref.path, doc_type, exc
                )
                continue

        logger.info(
            "Generated %s item(s) from %s file(s)", len(items), len(policy_refs)
        )
        return items

    def _process_constitution_dir(self) -> list[VectorizableItem]:
        """
        Process constitution directory files.

        Constitution files are not indexed by IntentRepository's policy index,
        so we use direct directory resolution through IntentRepository.root.

        Returns:
            List of VectorizableItem objects
        """
        constitution_dir = self.intent_repo.root / "constitution"

        if not constitution_dir.exists():
            logger.warning("Constitution directory not found: %s", constitution_dir)
            return []

        files = self._collect_files(constitution_dir, recursive=True)
        if not files:
            logger.info("No constitution files found")
            return []

        logger.info("Processing %s constitution file(s)", len(files))

        items: list[VectorizableItem] = []
        for file_path in files:
            try:
                # Load through IntentRepository for consistency
                data = self.intent_repo.load_document(file_path)

                if not isinstance(data, dict):
                    logger.warning(
                        "Skipping non-dict document: %s (type=%s)",
                        file_path,
                        type(data).__name__,
                    )
                    continue

                # Transform to VectorizableItems (delegates to item_builder)
                file_items = data_to_items(
                    data,
                    file_path,
                    doc_type="constitution",
                    key_root="constitution",
                    intent_root=self.intent_repo.root,
                )
                items.extend(file_items)

            except Exception as exc:
                logger.exception(
                    "Failed to process constitution file %s: %s", file_path, exc
                )
                continue

        logger.info("Generated %s item(s) from %s file(s)", len(items), len(files))
        return items

    def _collect_files(self, directory: Path, recursive: bool) -> list[Path]:
        """
        Collect JSON/YAML files from directory.

        This is only used for constitution directory since those files
        are not in the policy index.

        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively

        Returns:
            Sorted list of file paths
        """
        collected: set[Path] = set()
        for ext in self._EXTENSIONS:
            if recursive:
                collected.update(p for p in directory.rglob(f"*{ext}") if p.is_file())
            else:
                collected.update(p for p in directory.glob(f"*{ext}") if p.is_file())
        return sorted(collected)
