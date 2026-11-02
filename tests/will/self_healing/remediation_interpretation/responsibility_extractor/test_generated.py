from __future__ import annotations

from unittest.mock import MagicMock

from will.self_healing.remediation_interpretation.responsibility_extractor import (
    ResponsibilityExtractor,
)


# ID: 1a6ce17f-1fda-4aea-8544-03b168176ea9
def test_ResponsibilityExtractor_extract():
    extractor = ResponsibilityExtractor()

    cluster_a = MagicMock(name="cluster_a")
    cluster_a.priority = 1
    cluster_a.confidence = 2
    cluster_b = MagicMock(name="cluster_b")
    cluster_b.priority = 2
    cluster_b.confidence = 1
    cluster_c = MagicMock(name="cluster_c")
    cluster_c.priority = 3
    cluster_c.confidence = 3

    role_cluster = MagicMock(name="role_cluster")
    import_cluster = MagicMock(name="import_cluster")
    violation_cluster = MagicMock(name="violation_cluster")

    extractor._build_role_cluster = MagicMock(return_value=role_cluster)
    extractor._build_import_cluster = MagicMock(return_value=import_cluster)
    extractor._build_symbol_clusters = MagicMock(return_value=[cluster_a, cluster_b])
    extractor._build_violation_pressure_cluster = MagicMock(
        return_value=violation_cluster
    )
    extractor._merge_compatible_clusters = MagicMock(
        return_value=[
            role_cluster,
            import_cluster,
            cluster_a,
            cluster_b,
            violation_cluster,
        ]
    )
    extractor._sort_key = MagicMock(side_effect=lambda c: 0)

    file_context = {
        "top_level_symbols": [{"name": "Foo"}, {"name": "Bar"}],
        "imports": ["os", "sys"],
        "file_role": {"role": "service"},
        "file_metrics": {"loc": 120},
        "violation_summary": {"count": 2},
    }

    result = extractor.extract(file_context)

    assert result == [
        role_cluster,
        import_cluster,
        cluster_a,
        cluster_b,
        violation_cluster,
    ]
    extractor._build_role_cluster.assert_called_once_with(
        file_context["file_role"],
        file_context["file_metrics"],
        file_context["violation_summary"],
    )
    extractor._build_import_cluster.assert_called_once_with(file_context["imports"])
    extractor._build_symbol_clusters.assert_called_once_with(
        file_context["top_level_symbols"]
    )
    extractor._build_violation_pressure_cluster.assert_called_once_with(
        metrics=file_context["file_metrics"],
        violation_summary=file_context["violation_summary"],
    )
    extractor._merge_compatible_clusters.assert_called_once()




# ID: ea7f3cf6-3545-49da-8e1d-d9293b59abaa
def test_ResponsibilityExtractor():
    extractor = ResponsibilityExtractor()

    file_context = {
        "top_level_symbols": [
            {"name": "MyService", "symbol_type": "class", "bases": ["BaseService"]},
            {"name": "run", "symbol_type": "function", "is_async": False},
        ],
        "imports": [
            {"module": "shared.utils"},
            {"module": "will.core"},
            {"module": "body.services"},
            {"module": "mind.agents"},
        ],
        "file_role": {
            "role_id": "service",
            "layer": "application",
            "evidence": ["naming"],
        },
        "file_metrics": {
            "finding_count": 3,
            "distinct_rule_count": 2,
        },
        "violation_summary": {
            "rules": {"max_file_size": 2, "modularity": 1},
        },
    }

    clusters = extractor.extract(file_context)

    assert isinstance(clusters, list)
    assert clusters, "Expected at least one responsibility cluster"

    names = [cluster.name for cluster in clusters]
    assert "architectural_role" in names
    assert "dependency_surface" in names
    assert "violation_pressure" in names

    # Deterministic ordering: sorted by (name, summary)
    sort_keys = [(c.name, c.summary) for c in clusters]
    assert sort_keys == sorted(sort_keys)

    for cluster in clusters:
        assert isinstance(cluster.name, str) and cluster.name
        assert isinstance(cluster.summary, str)
        assert isinstance(cluster.evidence, list)
        assert isinstance(cluster.symbols, list)

    role_cluster = next(c for c in clusters if c.name == "architectural_role")
    assert "service" in role_cluster.summary
    assert "application" in role_cluster.summary
    assert role_cluster.evidence == ["naming"]

    violation_cluster = next(c for c in clusters if c.name == "violation_pressure")
    assert any("max_file_size" in e for e in violation_cluster.evidence)

    # Empty context yields no role/import/violation clusters
    empty_clusters = extractor.extract({})
    assert empty_clusters == []
