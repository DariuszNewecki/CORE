# src/shared/self_healing/remediation_interpretation/strategy_selector.py

from __future__ import annotations

from typing import Any

from shared.self_healing.remediation_interpretation.models import (
    FileRole,
    RemediationStrategy,
    ResponsibilityCluster,
)
from shared.self_healing.remediation_interpretation.strategy_catalog import (
    StrategyCatalog,
    StrategyTemplate,
)


# Minimum score for choose_recommended to return a strategy.
# A strategy scoring below this has insufficient evidence to be recommended.
# The caller must handle None and surface it for human review.
_MIN_RECOMMENDED_SCORE = 15


# ID: c33cf1f8-f7a4-4b6f-a8c4-e63c77927392
class StrategySelector:
    """
    Deterministically rank remediation strategies for a violating file.

    This selector evaluates a bounded catalog of known strategies against:
    - detected file role
    - responsibility clusters
    - file metrics
    - violation summary

    Output is a ranked list of RemediationStrategy objects ready to be
    embedded into a ReasoningBrief.

    choose_recommended() may return None when no strategy scores above the
    minimum threshold. Callers must handle this — it is a valid governance
    outcome indicating that autonomous strategy selection is inappropriate
    and human review is required.

    Design constraints:
    - deterministic only
    - no LLM
    - no file access
    - no repo traversal
    - bounded strategy vocabulary
    """

    def __init__(self, strategy_catalog: StrategyCatalog | None = None) -> None:
        self._catalog = strategy_catalog or StrategyCatalog()

    # ID: 4fb9f7e4-3270-497d-a5c0-a9c914c69f69
    def select(
        self,
        file_role: FileRole,
        file_context: dict[str, Any],
        responsibility_clusters: list[ResponsibilityCluster],
    ) -> list[RemediationStrategy]:
        """
        Rank all candidate strategies and return them in descending score order.
        """
        templates = self._catalog.list_templates()
        scored: list[tuple[int, list[str], StrategyTemplate]] = []

        for template in templates:
            score, evidence = self._score_template(
                template=template,
                file_role=file_role,
                file_context=file_context,
                responsibility_clusters=responsibility_clusters,
            )
            scored.append((score, evidence, template))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            RemediationStrategy(
                strategy_id=t.strategy_id,
                summary=t.summary,
                rationale=t.rationale,
                risk_level=t.risk_level,
                preserves_contract=t.preserves_contract,
                evidence=ev,
                score=sc,
            )
            for sc, ev, t in scored
        ]

    # ID: 976bc69b-291b-41c0-843d-1b5d233fe417
    def choose_recommended(
        self,
        candidate_strategies: list[RemediationStrategy],
    ) -> RemediationStrategy | None:
        """
        Return the top-ranked strategy if it meets the minimum score threshold.

        Returns None when:
        - candidate_strategies is empty
        - the top strategy scores below _MIN_RECOMMENDED_SCORE

        A None return is a valid governance signal: it means the evidence
        is insufficient to confidently recommend any automated strategy.
        The caller should surface this for human review rather than
        substituting a guess.
        """
        if not candidate_strategies:
            return None

        top = candidate_strategies[0]
        if top.score < _MIN_RECOMMENDED_SCORE:
            return None

        return top

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_template(
        self,
        template: StrategyTemplate,
        file_role: FileRole,
        file_context: dict[str, Any],
        responsibility_clusters: list[ResponsibilityCluster],
    ) -> tuple[int, list[str]]:
        """Score a single strategy template against the current file context."""
        score = 0
        evidence: list[str] = []

        metrics = dict(file_context.get("file_metrics") or {})
        violation_summary = dict(file_context.get("violation_summary") or {})
        role_constraints = list(file_context.get("role_constraints") or [])

        role_score, role_evidence = self._score_role_alignment(template, file_role)
        score += role_score
        evidence.extend(role_evidence)

        rule_score, rule_evidence = self._score_rule_alignment(
            template,
            violation_summary,
        )
        score += rule_score
        evidence.extend(rule_evidence)

        metric_score, metric_evidence = self._score_metrics(template, metrics)
        score += metric_score
        evidence.extend(metric_evidence)

        cluster_score, cluster_evidence = self._score_clusters(
            template,
            responsibility_clusters,
        )
        score += cluster_score
        evidence.extend(cluster_evidence)

        constraint_score, constraint_evidence = self._score_constraints(
            template,
            role_constraints,
            file_role,
        )
        score += constraint_score
        evidence.extend(constraint_evidence)

        conservative_score, conservative_evidence = self._score_conservatism(
            template,
            file_role,
            metrics,
            responsibility_clusters,
        )
        score += conservative_score
        evidence.extend(conservative_evidence)

        evidence.append(f"Deterministic strategy score={score}.")
        return score, self._dedupe_preserve_order(evidence)

    # ID: 5a11f92f-57d6-4b0e-8b7c-fc4e1a5a83dd
    def _score_role_alignment(
        self,
        template: StrategyTemplate,
        file_role: FileRole,
    ) -> tuple[int, list[str]]:
        """Score alignment with detected file role."""
        score = 0
        evidence: list[str] = []
        role_id = file_role.role_id

        if role_id in template.preferred_for_roles:
            score += 25
            evidence.append(f"Preferred for detected role '{role_id}'.")
        elif self._generalized_worker_match(role_id, template.preferred_for_roles):
            score += 16
            evidence.append(
                f"Preferred for generalized worker role matching '{role_id}'."
            )

        if role_id in template.discouraged_for_roles:
            score -= 25
            evidence.append(f"Discouraged for detected role '{role_id}'.")

        if file_role.layer in {"mind", "will", "body", "shared"}:
            evidence.append(f"Detected constitutional layer is '{file_role.layer}'.")

        return score, evidence

    # ID: 294615fb-87f4-4f17-88d4-4dd4049c5f0c
    def _score_rule_alignment(
        self,
        template: StrategyTemplate,
        violation_summary: dict[str, Any],
    ) -> tuple[int, list[str]]:
        """Score alignment with violated rules."""
        score = 0
        evidence: list[str] = []

        for rule_id in violation_summary:
            if rule_id in template.preferred_for_rules:
                score += 12
                evidence.append(f"Preferred for violated rule '{rule_id}'.")
            if rule_id in template.discouraged_for_rules:
                score -= 12
                evidence.append(f"Discouraged for violated rule '{rule_id}'.")

        return score, evidence

    def _score_metrics(
        self,
        template: StrategyTemplate,
        metrics: dict[str, Any],
    ) -> tuple[int, list[str]]:
        """Score based on file size metrics."""
        score = 0
        evidence: list[str] = []

        line_count = int(metrics.get("line_count", 0) or 0)

        if line_count > 400 and template.strategy_id in {
            "split_module_by_responsibility",
            "extract_service_collaborator",
            "extract_analysis_service",
        }:
            score += 10
            evidence.append(
                f"File is large ({line_count} lines); structural strategies favored."
            )

        if line_count < 200 and template.strategy_id in {
            "split_module_by_responsibility",
        }:
            score -= 10
            evidence.append(
                f"File is small ({line_count} lines); split strategy discouraged."
            )

        return score, evidence

    def _score_clusters(
        self,
        template: StrategyTemplate,
        responsibility_clusters: list[ResponsibilityCluster],
    ) -> tuple[int, list[str]]:
        """Score based on detected responsibility clusters."""
        score = 0
        evidence: list[str] = []
        cluster_count = len(responsibility_clusters)

        if cluster_count >= 3 and template.strategy_id in {
            "split_module_by_responsibility",
            "extract_service_collaborator",
        }:
            score += 8
            evidence.append(
                f"{cluster_count} responsibility clusters detected; "
                "structural split strategies favored."
            )

        if cluster_count <= 1 and template.strategy_id in {
            "split_module_by_responsibility",
        }:
            score -= 8
            evidence.append("Few clusters detected; split strategy discouraged.")

        return score, evidence

    def _score_constraints(
        self,
        template: StrategyTemplate,
        role_constraints: list[str],
        file_role: FileRole,
    ) -> tuple[int, list[str]]:
        """Score alignment with role constraints."""
        score = 0
        evidence: list[str] = []

        if file_role.role_id in {"repository", "model"}:
            if template.strategy_id == "preserve_role_extract_helpers_only":
                score += 9
                evidence.append(
                    f"Conservative role-preserving strategy fits role "
                    f"'{file_role.role_id}'."
                )
            if template.strategy_id in {
                "extract_service_collaborator",
                "extract_analysis_service",
            }:
                score -= 8
                evidence.append(
                    f"Cross-boundary extraction is less suitable for role "
                    f"'{file_role.role_id}'."
                )

        return score, evidence

    # ID: 487651f1-a9f6-4622-9162-f2bb0d590c23
    def _score_conservatism(
        self,
        template: StrategyTemplate,
        file_role: FileRole,
        metrics: dict[str, Any],
        responsibility_clusters: list[ResponsibilityCluster],
    ) -> tuple[int, list[str]]:
        """
        Bias toward the least invasive effective strategy when evidence for a
        larger structural split is weak.
        """
        score = 0
        evidence: list[str] = []

        line_count = int(metrics.get("line_count", 0) or 0)
        cluster_count = len(responsibility_clusters)
        strong_split_case = (
            line_count >= 450
            and cluster_count >= 4
            and any(item.name == "mixed_surface" for item in responsibility_clusters)
        )

        if not strong_split_case and template.strategy_id in {
            "defer_structural_split_choose_local_cleanup",
            "preserve_role_extract_helpers_only",
            "extract_helper_functions",
            "extract_private_methods",
        }:
            score += 8
            evidence.append(
                "Conservative bias applied because evidence for aggressive "
                "structural split is limited."
            )

        if (
            strong_split_case
            and template.strategy_id == "split_module_by_responsibility"
        ):
            score += 14
            evidence.append("Strong split case detected from size and cluster spread.")

        if (
            file_role.role_id in {"worker.sensor", "worker.actor"}
            and template.preserves_contract
        ):
            score += 5
            evidence.append(
                "Contract-preserving strategy is favorable for worker remediation."
            )

        return score, evidence

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    # ID: 7747ed4c-4f92-4f93-89a1-b6f83a37a8e8
    def _generalized_worker_match(
        self,
        role_id: str,
        preferred_roles: tuple[str, ...],
    ) -> bool:
        """Allow worker.* roles to match generic worker preference."""
        return role_id.startswith("worker.") and any(
            pr.startswith("worker.") for pr in preferred_roles
        )

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        """Deduplicate strings while preserving original order."""
        seen: set[str] = set()
        output: list[str] = []

        for item in items:
            if item not in seen:
                seen.add(item)
                output.append(item)

        return output
