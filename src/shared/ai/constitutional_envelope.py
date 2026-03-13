# src/shared/ai/constitutional_envelope.py
# ID: ce-core-001
"""
ConstitutionalEnvelope — automatic law injection for every LLM call.

Resolves applicable .intent/ rules for a given task scope and formats
them as a structured constraints block injected into every PromptModel
system prompt.

Design principle: Law travels with jurisdiction, not with the brief.
The task prompt (system.txt / user.txt) stays narrow and purposeful.
Constitutional constraints are assembled automatically from .intent/
based on which layers the task touches — the caller never specifies them.

Analogous to:
  - Kubernetes AdmissionController (policy injected at request time)
  - OPA (policy evaluated separately from the request)
  - Compiler type system (law embedded in the toolchain, not the source)
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ---------------------------------------------------------------------------
# Layer resolution
# ---------------------------------------------------------------------------

# File path prefix → canonical layer name
_LAYER_MAP: dict[str, str] = {
    "src/body/": "body",
    "src/will/": "will",
    "src/mind/": "mind",
    "src/shared/": "shared",
    "src/cli/": "cli",
}

# Rule policy categories always injected regardless of layer
_ALWAYS_INCLUDE_CATEGORIES: frozenset[str] = frozenset({"code", "logic", "ai"})

# Enforcement levels included in the envelope (advisory is omitted — informational only)
_INCLUDE_ENFORCEMENT: frozenset[str] = frozenset({"blocking", "reporting"})

# Authority → sort precedence (lower = higher authority, injected first)
_AUTHORITY_ORDER: dict[str, int] = {
    "constitution": 0,
    "policy": 1,
    "advisory": 2,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


# ID: ce-core-002
def _resolve_layers(target_files: list[str]) -> set[str]:
    """
    Derive the set of architectural layers touched by target_files.

    Falls back to 'shared' when a file does not match any known prefix.
    """
    layers: set[str] = set()
    for f in target_files:
        f_norm = f.replace("\\", "/")
        matched = False
        for prefix, layer in _LAYER_MAP.items():
            if f_norm.startswith(prefix):
                layers.add(layer)
                matched = True
                break
        if not matched:
            layers.add("shared")
    return layers


# ID: ce-core-003
def _rule_category(policy_name: str) -> str:
    """
    Extract the top-level category from a policy_name.

    Example: 'code/purity' → 'code', 'architecture/layers' → 'architecture'
    """
    return policy_name.split("/")[0] if policy_name else ""


# ID: ce-core-004
def _is_relevant(rule_entry: dict[str, Any], layers: set[str]) -> bool:
    """
    Decide whether a rule applies to the given task scope.

    Inclusion logic:
    1. Skip advisory enforcement — too noisy, not law.
    2. Always include: code, logic, ai categories.
    3. Include architecture rules when multiple layers are touched.
    4. Include rules whose category matches a touched layer.
    """
    rule = rule_entry.get("rule", {})
    enforcement = rule.get("enforcement", "advisory")
    if enforcement not in _INCLUDE_ENFORCEMENT:
        return False

    category = _rule_category(rule_entry.get("policy_name", ""))

    if category in _ALWAYS_INCLUDE_CATEGORIES:
        return True

    if category == "architecture" and len(layers) > 1:
        return True

    if category in layers:
        return True

    return False


# ID: ce-core-005
def _format_envelope(rules: list[dict[str, Any]], layers: set[str]) -> str:
    """
    Render the constitutional constraints block for injection into system prompt.

    Groups rules by category, ordered by authority precedence.
    """
    if not rules:
        return ""

    lines: list[str] = [
        "## Constitutional Constraints",
        "",
        f"Task scope — layers: {', '.join(sorted(layers))}",
        "",
        "The following rules are NON-NEGOTIABLE. Every line of code you generate",
        "MUST comply. Violations will be detected by the constitutional audit and",
        "will block deployment.",
        "",
    ]

    current_category: str | None = None
    for entry in rules:
        category = _rule_category(entry["policy_name"])
        rule = entry["rule"]

        if category != current_category:
            lines.append(f"### {category.upper()}")
            current_category = category

        rule_id = rule.get("id", "unknown")
        statement = rule.get("statement", "").strip()
        enforcement = rule.get("enforcement", "advisory")
        authority = rule.get("authority", "policy")

        marker = "⛔ BLOCKING" if enforcement == "blocking" else "⚠️  REQUIRED"
        lines.append(f"- [{marker}] `{rule_id}` (authority: {authority})")
        if statement:
            lines.append(f"  {statement}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ID: ce-core-006
# ID: 91053934-daa1-4409-9d14-ae69ba6f69f0
class ConstitutionalEnvelope:
    """
    Resolved constitutional constraints for a specific LLM task scope.

    Produced by ConstitutionalEnvelope.build() — do not construct directly.

    Attributes:
        text:       Formatted constraints block ready for system prompt injection.
                    Empty string if no applicable rules found or on load failure.
        rule_count: Number of unique rules injected.
        layers:     Architectural layers resolved from target_files.
    """

    def __init__(self, text: str, rule_count: int, layers: set[str]) -> None:
        self.text = text
        self.rule_count = rule_count
        self.layers = layers

    # ID: ce-core-007
    @classmethod
    # ID: 409ad4cd-d001-4613-972f-9488a5d7f0e7
    def build(cls, target_files: list[str]) -> ConstitutionalEnvelope:
        """
        Build the constitutional envelope for the given target files.

        Queries IntentRepository for all active rules, filters to those
        applicable to the layers touched by target_files, deduplicates,
        sorts by authority precedence, and returns the formatted envelope.

        Args:
            target_files: File paths the LLM will generate or modify.
                          Used to resolve which layers are in scope.

        Returns:
            ConstitutionalEnvelope ready for injection. On any IntentRepository
            failure, returns an empty envelope (fail-open) and logs a warning.
        """
        if not target_files:
            return cls(text="", rule_count=0, layers=set())

        layers = _resolve_layers(target_files)

        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            repo = get_intent_repository()
            all_rules = repo.list_policy_rules()
        except Exception as e:
            logger.warning(
                "ConstitutionalEnvelope: IntentRepository unavailable (%s). "
                "Proceeding without constitutional envelope.",
                e,
            )
            return cls(text="", rule_count=0, layers=layers)

        # Filter
        relevant = [r for r in all_rules if _is_relevant(r, layers)]

        # Sort: authority precedence → category → rule id (stable)
        relevant.sort(
            key=lambda r: (
                _AUTHORITY_ORDER.get(r["rule"].get("authority", "advisory"), 99),
                _rule_category(r.get("policy_name", "")),
                r["rule"].get("id", ""),
            )
        )

        # Deduplicate by rule id — same rule may appear across policy files
        seen_ids: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for entry in relevant:
            rule_id = entry["rule"].get("id", "")
            if rule_id and rule_id not in seen_ids:
                seen_ids.add(rule_id)
                deduped.append(entry)

        text = _format_envelope(deduped, layers)

        logger.debug(
            "ConstitutionalEnvelope: %d rules injected for layers %s",
            len(deduped),
            sorted(layers),
        )

        return cls(text=text, rule_count=len(deduped), layers=layers)

    # ID: ce-core-008
    @classmethod
    # ID: 105403a7-ebdd-45a0-9971-bd0b9a4432c1
    def empty(cls) -> ConstitutionalEnvelope:
        """Return an empty envelope (no-op injection)."""
        return cls(text="", rule_count=0, layers=set())
