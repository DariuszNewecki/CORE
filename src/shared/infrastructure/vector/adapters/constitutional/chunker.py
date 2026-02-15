# src/shared/infrastructure/vector/adapters/constitutional/chunker.py

"""
Constitutional Document Chunker

Pure functions for splitting constitutional documents into semantic chunks.
Each chunk represents a meaningful section for vector search.

Design:
- Input: Raw document dict (from YAML/JSON)
- Output: List of chunk dicts with section_type, section_path, content
- Zero dependencies on filesystem or IntentRepository
- Stateless, deterministic transformations
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.vector.adapters.constitutional.utils import safe_str
from shared.processors.yaml_processor import strict_yaml_processor


# ID: 73e72340-4428-4517-a7b6-55f63d7b6d72
# ID: 8a7b6c5d-4e3f-2a1b-9c8d-7e6f5a4b3c2d
def chunk_document(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Chunk a constitutional document into semantic sections.

    Processes standard constitutional document structure:
    - title + purpose → purpose chunk
    - philosophy → philosophy chunk
    - requirements → requirement chunks (one per requirement)
    - rules → rule chunks (one per rule)
    - validation_rules → validation_rule chunks
    - examples → example chunks

    Args:
        data: Parsed document dict from YAML/JSON

    Returns:
        List of chunk dicts, each containing:
        - section_type: Type of content (purpose, rule, requirement, etc.)
        - section_path: Hierarchical path (e.g., "rules.purity.stable_id")
        - content: Text content for vectorization
        - severity: Optional severity level (for rules)
    """
    chunks: list[dict[str, Any]] = []

    title = safe_str(data.get("title")).strip()
    purpose = safe_str(data.get("purpose")).strip()
    if title and purpose:
        chunks.append(
            {
                "section_type": "purpose",
                "section_path": "purpose",
                "content": f"{title}\n\n{purpose}",
            }
        )

    philosophy = safe_str(data.get("philosophy")).strip()
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
        chunks.extend(_chunk_requirements(requirements))

    rules = data.get("rules")
    if isinstance(rules, list):
        chunks.extend(_chunk_rules(rules))

    validation_rules = data.get("validation_rules")
    if isinstance(validation_rules, list):
        chunks.extend(_chunk_validation_rules(validation_rules))

    examples = data.get("examples")
    if isinstance(examples, dict):
        chunks.extend(_chunk_examples(examples))

    return chunks


# ID: 0da3a670-5ce7-4978-a9c6-ee450783859c
# ID: 9b8a7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c4d
def _chunk_requirements(requirements: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Chunk requirements section.

    Each requirement becomes a separate chunk with:
    - mandate (required statement)
    - implementation (optional guidance)

    Args:
        requirements: Requirements dict from document

    Returns:
        List of requirement chunks
    """
    chunks: list[dict[str, Any]] = []
    for req_name, req_data in requirements.items():
        if not isinstance(req_name, str) or not isinstance(req_data, dict):
            continue
        mandate = safe_str(req_data.get("mandate")).strip()
        if not mandate:
            continue

        content = f"{mandate}\n"
        impl = req_data.get("implementation")
        if impl is not None:
            content += "\nImplementation:\n"
            if isinstance(impl, list):
                lines = [safe_str(x).strip() for x in impl if x is not None]
                lines = [x for x in lines if x]
                content += "\n".join(f"- {x}" for x in lines)
            else:
                content += safe_str(impl).strip()

        chunks.append(
            {
                "section_type": "requirement",
                "section_path": f"requirements.{req_name}",
                "content": content,
                "severity": "error",
            }
        )
    return chunks


# ID: 0fb9ba81-1703-4c18-a888-ffd4d19f8a63
# ID: 0ace5097-e5fd-4cbe-922f-2d44965b4682
def _chunk_rules(rules: list[Any]) -> list[dict[str, Any]]:
    """
    Chunk rules section.

    Each rule becomes a chunk with:
    - Rule ID
    - Statement (the actual rule)
    - Enforcement level

    Args:
        rules: List of rule dicts

    Returns:
        List of rule chunks
    """
    chunks: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        statement = safe_str(rule.get("statement")).strip()
        if not statement:
            continue

        rule_id = safe_str(rule.get("id")) or "unknown"
        enforcement = safe_str(rule.get("enforcement")) or "error"
        content = f"Rule: {rule_id}\nStatement: {statement}\nEnforcement: {enforcement}"
        chunks.append(
            {
                "section_type": "rule",
                "section_path": f"rules.{rule_id}",
                "content": content,
                "severity": enforcement,
            }
        )
    return chunks


# ID: 65e6ea48-d23d-4895-9833-f996d0482023
# ID: 0ac38395-9bfd-4b29-abb0-7fae7f020c6d
def _chunk_validation_rules(rules: list[Any]) -> list[dict[str, Any]]:
    """
    Chunk validation rules section.

    Validation rules describe runtime checks with:
    - Rule name
    - Description
    - Severity
    - Enforcement phase

    Args:
        rules: List of validation rule dicts

    Returns:
        List of validation_rule chunks
    """
    chunks: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue

        rule_name = safe_str(rule.get("rule")).strip()
        if not rule_name:
            continue

        description = safe_str(rule.get("description")).strip()
        severity = safe_str(rule.get("severity")) or "error"
        enforcement = safe_str(rule.get("enforcement")) or "runtime"
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


# ID: b54c962f-0e5f-436a-8f18-f5d9d4fee351
# ID: b8f311e1-d339-414b-b3aa-d5f98927b976
def _chunk_examples(examples: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Chunk examples section.

    Each example becomes a chunk with YAML representation
    of the example data.

    Args:
        examples: Examples dict from document

    Returns:
        List of example chunks
    """
    chunks: list[dict[str, Any]] = []
    for example_name, example_data in examples.items():
        if not isinstance(example_name, str) or not isinstance(example_data, dict):
            continue
        content = (
            f"Example: {example_name}\n{strict_yaml_processor.dump_yaml(example_data)}"
        )
        chunks.append(
            {
                "section_type": "example",
                "section_path": f"examples.{example_name}",
                "content": content,
            }
        )
    return chunks
