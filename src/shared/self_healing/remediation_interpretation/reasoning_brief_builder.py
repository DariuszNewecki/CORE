# src/shared/self_healing/remediation_interpretation/reasoning_brief_builder.py

from __future__ import annotations

from typing import Any

from shared.self_healing.remediation_interpretation.models import (
    FileRole,
    NormalizedFinding,
    ReasoningBrief,
    RemediationStrategy,
    ResponsibilityCluster,
)


# ID: 62a7d7e8-c9ef-4d22-b6ce-8e6a18a6d7c1
class ReasoningBriefBuilder:
    """
    Build a bounded deterministic ReasoningBrief.

    This builder converts the outputs of the deterministic interpretation
    layer into the governed planning artifact that will later be passed into
    the existing PromptModel-based remediation path.

    Design constraints:
    - deterministic only
    - no LLM
    - no file access
    - no repo traversal
    - concise, explainable output
    """

    # ID: 3d6af7a4-e3d0-4fc4-9340-3c1d655afc9b
    def build(
        self,
        file_path: str,
        file_role: FileRole,
        normalized_findings: list[NormalizedFinding],
        file_context: dict[str, Any],
        responsibility_clusters: list[ResponsibilityCluster],
        candidate_strategies: list[RemediationStrategy],
        recommended_strategy: RemediationStrategy | None,
    ) -> ReasoningBrief:
        """
        Build the final reasoning brief from already-computed interpretation
        data.
        """
        constraints = self._build_constraints(
            file_role=file_role,
            file_context=file_context,
            recommended_strategy=recommended_strategy,
        )
        architectural_notes = self._build_architectural_notes(
            file_path=file_path,
            file_role=file_role,
            normalized_findings=normalized_findings,
            file_context=file_context,
            responsibility_clusters=responsibility_clusters,
            recommended_strategy=recommended_strategy,
        )

        return ReasoningBrief(
            file_path=file_path,
            file_role=file_role,
            findings=list(normalized_findings),
            responsibility_clusters=list(responsibility_clusters),
            candidate_strategies=list(candidate_strategies),
            recommended_strategy=recommended_strategy,
            constraints=constraints,
            architectural_notes=architectural_notes,
        )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    # ID: 7fdcc252-c434-4b56-a615-8d0e68cbb6b5
    def _build_constraints(
        self,
        file_role: FileRole,
        file_context: dict[str, Any],
        recommended_strategy: RemediationStrategy | None,
    ) -> list[str]:
        """
        Build bounded planning constraints for downstream proposal generation.
        """
        constraints: list[str] = []

        role_constraints = list(file_context.get("role_constraints") or [])
        constraints.extend(role_constraints)

        if file_role.layer != "unknown":
            constraints.append(
                f"Do not relocate the file outside the "
                f"'{file_role.layer}' constitutional layer."
            )

        if file_role.role_id != "unknown":
            constraints.append(
                f"Preserve the file's primary architectural role as "
                f"'{file_role.role_id}'."
            )

        if recommended_strategy is not None and recommended_strategy.preserves_contract:
            constraints.append(
                "Preserve externally visible behavior and current contracts."
            )

        if file_role.role_id == "worker.sensor":
            constraints.append("Do not introduce mutation, apply, or commit behavior.")
            constraints.append(
                "Do not introduce proposal-generation responsibility into sensing flow."
            )
        elif file_role.role_id == "worker.actor":
            constraints.append(
                "Preserve crate/canary/apply orchestration responsibilities."
            )
            constraints.append(
                "Do not move acting behavior into will-layer sensing surfaces."
            )
        elif file_role.role_id == "route":
            constraints.append(
                "Do not accumulate business logic in routing/controller surfaces."
            )
        elif file_role.role_id == "repository":
            constraints.append(
                "Do not mix data access boundaries with orchestration concerns."
            )
        elif file_role.role_id == "model":
            constraints.append(
                "Keep model surfaces declarative; avoid orchestration creep."
            )

        return self._dedupe_preserve_order(constraints)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    # ID: ccd2d5de-f0ec-46f6-bf6e-6a2449c7bb7d
    def _build_architectural_notes(
        self,
        file_path: str,
        file_role: FileRole,
        normalized_findings: list[NormalizedFinding],
        file_context: dict[str, Any],
        responsibility_clusters: list[ResponsibilityCluster],
        recommended_strategy: RemediationStrategy | None,
    ) -> list[str]:
        """
        Build concise deterministic notes explaining the interpretation.
        """
        notes: list[str] = []

        metrics = dict(file_context.get("file_metrics") or {})
        violation_summary = dict(file_context.get("violation_summary") or {})
        structural_signals = list(file_context.get("structural_signals") or [])

        notes.append(
            f"File '{file_path}' is interpreted as role "
            f"'{file_role.role_id}' in layer '{file_role.layer}'."
        )

        line_count = int(metrics.get("line_count", 0) or 0)
        if line_count:
            notes.append(f"Current file size is {line_count} lines.")

        distinct_rule_count = int(metrics.get("distinct_rule_count", 0) or 0)
        finding_count = len(normalized_findings)
        if finding_count:
            notes.append(
                f"Remediation scope covers {finding_count} finding(s) across "
                f"{distinct_rule_count} distinct rule(s)."
            )

        dominant_rule = self._dominant_rule(violation_summary)
        if dominant_rule is not None:
            notes.append(
                f"Dominant remediation pressure comes from rule '{dominant_rule}'."
            )

        if responsibility_clusters:
            cluster_names = ", ".join(item.name for item in responsibility_clusters)
            notes.append(f"Detected responsibility clusters: {cluster_names}.")

        if structural_signals:
            for signal in structural_signals[:4]:
                notes.append(signal)

        if recommended_strategy is not None:
            notes.append(
                f"Recommended strategy is "
                f"'{recommended_strategy.strategy_id}': "
                f"{recommended_strategy.summary}"
            )

            for evidence_item in recommended_strategy.evidence[:4]:
                notes.append(f"Strategy evidence: {evidence_item}")

        return self._dedupe_preserve_order(notes)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    # ID: 72d1df0e-11f6-4f78-bcf3-0b5b5a4d1cc1
    def _dominant_rule(self, violation_summary: dict[str, Any]) -> str | None:
        """Return the most frequent violated rule, if any."""
        rules = dict(violation_summary.get("rules") or {})
        if not rules:
            return None

        best_rule: str | None = None
        best_count = -1

        for rule_id, count in rules.items():
            count_int = int(count)
            if count_int > best_count:
                best_rule = str(rule_id)
                best_count = count_int

        return best_rule

    # ID: 8b49b61e-e4c0-48d1-b0da-34d2d0cb6742
    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        """Deduplicate strings while preserving order."""
        seen: set[str] = set()
        output: list[str] = []

        for item in items:
            if item not in seen:
                seen.add(item)
                output.append(item)

        return output
