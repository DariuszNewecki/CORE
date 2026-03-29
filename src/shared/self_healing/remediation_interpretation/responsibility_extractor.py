# src/shared/self_healing/remediation_interpretation/responsibility_extractor.py

from __future__ import annotations

from typing import Any

from shared.self_healing.remediation_interpretation.models import ResponsibilityCluster


# ID: 2d31dc4e-c957-4cb6-b7c8-8d23d79dc0b4
class ResponsibilityExtractor:
    """
    Deterministically infer responsibility clusters from assembled file context.

    This service does not attempt semantic understanding in the LLM sense.
    It groups visible structural signals into bounded responsibility areas
    that can support strategy selection for remediation.

    Input:
        file_context produced by FileContextAssembler

    Output:
        list[ResponsibilityCluster]

    Design constraints:
    - deterministic only
    - no file access
    - no repo traversal
    - no LLM
    """

    # ID: 7a7bf625-f32b-470b-9c40-95d1b0af8ce7
    def extract(self, file_context: dict[str, Any]) -> list[ResponsibilityCluster]:
        """
        Extract responsibility clusters from the bounded file context.
        """
        symbols = file_context.get("top_level_symbols", [])
        imports = file_context.get("imports", [])
        file_role = file_context.get("file_role", {})
        metrics = file_context.get("file_metrics", {})
        violation_summary = file_context.get("violation_summary", {})

        clusters: list[ResponsibilityCluster] = []

        role_cluster = self._build_role_cluster(file_role, metrics, violation_summary)
        if role_cluster is not None:
            clusters.append(role_cluster)

        import_cluster = self._build_import_cluster(imports)
        if import_cluster is not None:
            clusters.append(import_cluster)

        symbol_clusters = self._build_symbol_clusters(symbols)
        clusters.extend(symbol_clusters)

        violation_cluster = self._build_violation_pressure_cluster(
            metrics=metrics,
            violation_summary=violation_summary,
        )
        if violation_cluster is not None:
            clusters.append(violation_cluster)

        clusters = self._merge_compatible_clusters(clusters)
        clusters.sort(key=self._sort_key)
        return clusters

    # ------------------------------------------------------------------
    # Cluster builders
    # ------------------------------------------------------------------

    # ID: 25188d39-2e4f-41a1-b455-bfdfba53ee98
    def _build_role_cluster(
        self,
        file_role: dict[str, Any],
        metrics: dict[str, Any],
        violation_summary: dict[str, Any],
    ) -> ResponsibilityCluster | None:
        """
        Build a primary cluster from the detected architectural role.
        """
        role_id = str(file_role.get("role_id") or "unknown")
        layer = str(file_role.get("layer") or "unknown")
        evidence = list(file_role.get("evidence") or [])

        if role_id == "unknown" and layer == "unknown":
            return None

        summary = (
            f"Primary architectural role appears to be '{role_id}' "
            f"within layer '{layer}'."
        )

        if metrics.get("finding_count", 0) > 0:
            summary += (
                f" Current remediation scope covers {metrics.get('finding_count', 0)} "
                "finding(s)."
            )

        rules = violation_summary.get("rules", {})
        if rules:
            summary += f" Violations are concentrated in {len(rules)} rule group(s)."

        return ResponsibilityCluster(
            name="architectural_role",
            summary=summary,
            evidence=evidence,
            symbols=[],
        )

    # ID: 3c9b4bd7-8a3e-4eb8-ac3f-17c6729e7c0b
    def _build_import_cluster(
        self,
        imports: list[dict[str, Any]],
    ) -> ResponsibilityCluster | None:
        """
        Build a cluster that captures dependency surface / import spread.
        """
        if not imports:
            return None

        module_names = sorted(
            {
                str(item.get("module") or item.get("name") or "").strip()
                for item in imports
                if str(item.get("module") or item.get("name") or "").strip()
            }
        )

        if not module_names:
            return None

        evidence: list[str] = []

        if len(module_names) >= 8:
            evidence.append("High import spread suggests broad dependency surface.")
        elif len(module_names) >= 4:
            evidence.append(
                "Moderate import spread suggests multiple collaboration points."
            )
        else:
            evidence.append("Limited import spread suggests narrow dependency surface.")

        shared_imports = [name for name in module_names if name.startswith("shared.")]
        will_imports = [name for name in module_names if name.startswith("will.")]
        body_imports = [name for name in module_names if name.startswith("body.")]
        mind_imports = [name for name in module_names if name.startswith("mind.")]

        if shared_imports:
            evidence.append(
                f"Imports shared layer dependencies ({len(shared_imports)})."
            )
        if will_imports:
            evidence.append(f"Imports will layer dependencies ({len(will_imports)}).")
        if body_imports:
            evidence.append(f"Imports body layer dependencies ({len(body_imports)}).")
        if mind_imports:
            evidence.append(f"Imports mind layer dependencies ({len(mind_imports)}).")

        summary = (
            "Dependency surface inferred from imports may represent a distinct "
            "responsibility area or collaboration burden."
        )

        return ResponsibilityCluster(
            name="dependency_surface",
            summary=summary,
            evidence=evidence,
            symbols=[],
        )

    # ID: 622d5f6d-dc5a-42c1-b646-6b8b900ac13e
    def _build_symbol_clusters(
        self,
        symbols: list[dict[str, Any]],
    ) -> list[ResponsibilityCluster]:
        """
        Build responsibility clusters from top-level symbol families.

        This is intentionally simple:
        - worker/service/repository-like classes
        - helper or orchestration function groups
        - mixed class/function surfaces
        """
        if not symbols:
            return []

        classes = [item for item in symbols if item.get("symbol_type") == "class"]
        functions = [
            item
            for item in symbols
            if item.get("symbol_type") in {"function", "async_function"}
        ]

        clusters: list[ResponsibilityCluster] = []

        if classes:
            class_names = [
                str(item.get("name") or "") for item in classes if item.get("name")
            ]
            class_evidence: list[str] = []

            if len(class_names) > 1:
                class_evidence.append(
                    "Multiple top-level classes indicate possible split responsibilities."
                )
            else:
                class_evidence.append(
                    "Single top-level class appears to anchor module behavior."
                )

            class_bases = sorted(
                {
                    base
                    for item in classes
                    for base in list(item.get("bases") or [])
                    if isinstance(base, str) and base
                }
            )
            if class_bases:
                class_evidence.append(
                    "Class inheritance surface detected: " + ", ".join(class_bases[:5])
                )

            clusters.append(
                ResponsibilityCluster(
                    name="class_surface",
                    summary="Top-level classes appear to define a distinct responsibility surface.",
                    evidence=class_evidence,
                    symbols=class_names,
                )
            )

        if functions:
            function_names = [
                str(item.get("name") or "") for item in functions if item.get("name")
            ]
            function_evidence: list[str] = []

            async_count = sum(1 for item in functions if item.get("is_async"))
            if async_count:
                function_evidence.append(
                    f"Module contains {async_count} async top-level function(s)."
                )

            if len(function_names) >= 5:
                function_evidence.append(
                    "Large top-level function surface suggests multiple operational concerns."
                )
            else:
                function_evidence.append(
                    "Top-level functions represent a bounded operational surface."
                )

            clusters.append(
                ResponsibilityCluster(
                    name="function_surface",
                    summary=(
                        "Top-level functions appear to define a distinct operational "
                        "or helper-oriented responsibility surface."
                    ),
                    evidence=function_evidence,
                    symbols=function_names,
                )
            )

        if classes and functions:
            mixed_symbols = [
                *(str(item.get("name") or "") for item in classes if item.get("name")),
                *(
                    str(item.get("name") or "")
                    for item in functions
                    if item.get("name")
                ),
            ]
            clusters.append(
                ResponsibilityCluster(
                    name="mixed_surface",
                    summary=(
                        "The module mixes top-level classes and top-level functions, "
                        "which may indicate multiple co-located responsibilities."
                    ),
                    evidence=[
                        "Mixed symbol surface detected.",
                        "Potential split point may exist between declarative structure and operational helpers.",
                    ],
                    symbols=mixed_symbols,
                )
            )

        return clusters

    # ID: 7749190d-873f-48cc-95c7-d6b20e6f5021
    def _build_violation_pressure_cluster(
        self,
        metrics: dict[str, Any],
        violation_summary: dict[str, Any],
    ) -> ResponsibilityCluster | None:
        """
        Build a cluster representing remediation pressure created by findings.

        This is useful for rules such as max_file_size, modularity, coupling,
        or mixed concerns where the violation pattern itself is informative.
        """
        finding_count = int(metrics.get("finding_count", 0) or 0)
        distinct_rule_count = int(metrics.get("distinct_rule_count", 0) or 0)
        rules = dict(violation_summary.get("rules") or {})

        if finding_count == 0:
            return None

        evidence: list[str] = [
            f"Remediation scope includes {finding_count} finding(s)."
        ]

        if distinct_rule_count > 1:
            evidence.append(
                f"Findings span {distinct_rule_count} distinct rules, suggesting broader structural pressure."
            )
        else:
            evidence.append("Findings are concentrated in a single rule family.")

        max_rule = None
        max_count = 0
        for rule_id, count in rules.items():
            if int(count) > max_count:
                max_rule = rule_id
                max_count = int(count)

        if max_rule:
            evidence.append(
                f"Dominant violation rule is '{max_rule}' with {max_count} finding(s)."
            )

        return ResponsibilityCluster(
            name="violation_pressure",
            summary=(
                "Violation pattern itself forms a planning-relevant responsibility "
                "cluster for remediation strategy selection."
            ),
            evidence=evidence,
            symbols=[],
        )

    # ------------------------------------------------------------------
    # Cluster merge
    # ------------------------------------------------------------------

    # ID: 80b169f9-1099-46fa-9bc8-843999b9e099
    def _merge_compatible_clusters(
        self,
        clusters: list[ResponsibilityCluster],
    ) -> list[ResponsibilityCluster]:
        """
        Merge very close clusters conservatively.

        We avoid aggressive merging because later strategy selection benefits
        from seeing distinct candidate responsibility areas.
        """
        output: list[ResponsibilityCluster] = []

        for cluster in clusters:
            existing = self._find_merge_target(output, cluster)
            if existing is None:
                output.append(cluster)
                continue

            existing.evidence = self._dedupe_preserve_order(
                [*existing.evidence, *cluster.evidence]
            )
            existing.symbols = self._dedupe_preserve_order(
                [*existing.symbols, *cluster.symbols]
            )

            if cluster.summary and cluster.summary not in existing.summary:
                existing.summary = f"{existing.summary} {cluster.summary}"

        return output

    # ID: 8c4d526d-43d6-4f91-a083-1f37fcb3efcb
    def _find_merge_target(
        self,
        current: list[ResponsibilityCluster],
        candidate: ResponsibilityCluster,
    ) -> ResponsibilityCluster | None:
        """Find a compatible existing cluster for conservative merging."""
        for item in current:
            if item.name == candidate.name:
                return item

            compatible = {
                ("class_surface", "mixed_surface"),
                ("function_surface", "mixed_surface"),
                ("mixed_surface", "class_surface"),
                ("mixed_surface", "function_surface"),
            }
            if (item.name, candidate.name) in compatible:
                return item

        return None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    # ID: 7f7e3787-9b82-48e8-94e5-e9af0d71f2cb
    def _sort_key(self, cluster: ResponsibilityCluster) -> tuple[str, str]:
        """Deterministic sort key for output clusters."""
        return (cluster.name, cluster.summary)

    # ID: 77d7c865-e495-422e-8d72-d38d517edc6f
    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        """Deduplicate strings while preserving original order."""
        seen: set[str] = set()
        output: list[str] = []

        for item in items:
            if item not in seen:
                seen.add(item)
                output.append(item)

        return output
