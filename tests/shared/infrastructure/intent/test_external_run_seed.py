"""shared.infrastructure.intent.external_run_seed -- #894 seeding unit (rulings A/D/E).

Pure model: closed-field parsing, deterministic refusals, manifest + seed_hash,
isolated-database-name defence in depth. No DB, no network (the digest probe
is exercised with a stubbed transport).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared.infrastructure.intent.external_run_seed import (
    SeedError,
    check_seed_serves_roles,
    load_seed_document,
    seed_hash,
    seed_manifest,
    validate_isolated_database_name,
)


def _seed(
    tmp_path: Path, *, resources=None, assignments=None, system_config=None
) -> Path:
    d = tmp_path / "seed"
    (d / "llm_resources").mkdir(parents=True)
    resources = (
        resources
        if resources is not None
        else [
            {
                "name": "ollama_qwen_coder_3b_trial",
                "env_prefix": "OLLAMA_QWEN_CODER_3B_TRIAL",
                "provided_capabilities": ["planning", "json_output"],
                "model_name": "qwen2.5-coder:3b",
                "model_digest": "f72c60cabf6237b07f6e",
                "api_url": "http://192.168.20.40:11434",
                "locality": "local",
                "is_available": True,
            }
        ]
    )
    for r in resources:
        (d / "llm_resources" / f"{r['name']}.yaml").write_text(yaml.safe_dump(r))
    (d / "assignments.yaml").write_text(
        yaml.safe_dump(
            {
                "assignments": assignments
                if assignments is not None
                else [
                    {
                        "role": "Planner",
                        "resource": "ollama_qwen_coder_3b_trial",
                        "priority": 1,
                        "is_active": True,
                    }
                ]
            }
        )
    )
    (d / "system_config.yaml").write_text(
        yaml.safe_dump(
            system_config
            if system_config is not None
            else {"operating_mode": "local_only", "llm_enabled": True}
        )
    )
    return d


PLANNER = {"Planner": frozenset({"planning"})}


def test_loads_a_well_formed_seed(tmp_path: Path) -> None:
    seed = load_seed_document(_seed(tmp_path))
    assert [r["name"] for r in seed.resources] == ["ollama_qwen_coder_3b_trial"]
    assert seed.assignments[0]["role"] == "Planner"
    assert set(seed.file_hashes) == {
        "llm_resources/ollama_qwen_coder_3b_trial.yaml",
        "assignments.yaml",
        "system_config.yaml",
    }
    check_seed_serves_roles(seed, PLANNER)


@pytest.mark.parametrize(
    "mutation, match",
    [
        (lambda d: (d / "assignments.yaml").unlink(), "missing"),
        (
            lambda d: (d / "assignments.yaml").write_text(
                "assignments: []\nextra: 1\n"
            ),
            "exactly one key",
        ),
        (
            lambda d: (d / "assignments.yaml").write_text(
                "assignments:\n- role: Planner\n  resource: nope\n  priority: 1\n  is_active: true\n"
            ),
            "does not define",
        ),
        (
            lambda d: (d / "assignments.yaml").write_text(
                "assignments:\n- role: Planner\n  resource: ollama_qwen_coder_3b_trial\n  priority: 1\n  is_active: true\n  note: x\n"
            ),
            "closed set",
        ),
        (
            lambda d: (d / "system_config.yaml").write_text(
                "operating_mode: hybrid\nllm_enabled: false\n"
            ),
            "llm_enabled must be true",
        ),
        (
            lambda d: (d / "system_config.yaml").write_text(
                "operating_mode: everywhere\nllm_enabled: true\n"
            ),
            "operating_mode",
        ),
        (
            lambda d: (d / "system_config.yaml").write_text(
                "operating_mode: hybrid\nllm_enabled: true\nrequest_timeout_seconds: 5\n"
            ),
            "closed set",
        ),
    ],
)
def test_shape_refusals(tmp_path: Path, mutation, match: str) -> None:
    d = _seed(tmp_path)
    mutation(d)
    with pytest.raises(SeedError, match=match):
        load_seed_document(d)


def test_no_resources_refused(tmp_path: Path) -> None:
    d = _seed(tmp_path)
    for f in (d / "llm_resources").iterdir():
        f.unlink()
    with pytest.raises(SeedError, match="no llm_resources"):
        load_seed_document(d)


def test_locality_excluded_by_operating_mode(tmp_path: Path) -> None:
    seed = load_seed_document(
        _seed(
            tmp_path,
            system_config={"operating_mode": "remote_only", "llm_enabled": True},
        )
    )
    with pytest.raises(SeedError, match="excluded by operating_mode"):
        check_seed_serves_roles(seed, PLANNER)


def test_remote_resource_without_secret_refused(tmp_path: Path) -> None:
    remote = {
        "name": "deepseek_trial",
        "env_prefix": "DEEPSEEK_TRIAL",
        "provided_capabilities": ["planning"],
        "model_name": "deepseek-chat",
        "api_url": "https://api.example",
        "locality": "remote",
        "is_available": True,
    }
    seed = load_seed_document(
        _seed(
            tmp_path,
            resources=[remote],
            assignments=[
                {
                    "role": "Planner",
                    "resource": "deepseek_trial",
                    "priority": 1,
                    "is_active": True,
                }
            ],
            system_config={"operating_mode": "hybrid", "llm_enabled": True},
        )
    )
    with pytest.raises(SeedError, match="api key"):
        check_seed_serves_roles(seed, PLANNER)
    check_seed_serves_roles(seed, PLANNER, secret_present=frozenset({"deepseek_trial"}))


def test_zero_qualified_and_no_assignment_refused(tmp_path: Path) -> None:
    seed = load_seed_document(_seed(tmp_path, assignments=[]))
    with pytest.raises(SeedError, match="no seeded resource provides"):
        check_seed_serves_roles(seed, {"Planner": frozenset({"planning", "vision"})})


def test_ambiguous_without_assignment_refused_and_assignment_resolves(
    tmp_path: Path,
) -> None:
    base = {
        "env_prefix": "X",
        "provided_capabilities": ["planning"],
        "model_name": "m",
        "api_url": "http://h:1",
        "locality": "local",
        "is_available": True,
    }
    two = [dict(base, name="a", env_prefix="A"), dict(base, name="b", env_prefix="B")]
    seed = load_seed_document(_seed(tmp_path, resources=two, assignments=[]))
    with pytest.raises(SeedError, match="ambiguous"):
        check_seed_serves_roles(seed, PLANNER)
    seed2 = load_seed_document(
        _seed(
            tmp_path / "again",
            resources=two,
            assignments=[
                {"role": "Planner", "resource": "b", "priority": 1, "is_active": True}
            ],
        )
    )
    check_seed_serves_roles(seed2, PLANNER)
    seed3 = load_seed_document(
        _seed(
            tmp_path / "tie",
            resources=two,
            assignments=[
                {"role": "Planner", "resource": "a", "priority": 1, "is_active": True},
                {"role": "Planner", "resource": "b", "priority": 1, "is_active": True},
            ],
        )
    )
    with pytest.raises(SeedError, match="more than one active priority-1"):
        check_seed_serves_roles(seed3, PLANNER)


def test_manifest_and_hash_are_deterministic(tmp_path: Path) -> None:
    seed = load_seed_document(_seed(tmp_path))
    kwargs = dict(
        verified_digests={"ollama_qwen_coder_3b_trial": "f72c60cabf6237b07f6e"},
        prompts=[
            {
                "id": "plan_goal",
                "source_commit": "abc",
                "files": {"model.yaml": "1" * 64},
            }
        ],
        roles=[{"role": "Planner", "taxonomy_sha256": "2" * 64}],
    )
    m1 = seed_manifest(seed, **kwargs)
    m2 = seed_manifest(load_seed_document(_seed(tmp_path / "copy")), **kwargs)
    assert seed_hash(m1) == seed_hash(m2)
    assert m1["resources"][0]["api_url_host"] == "192.168.20.40"
    assert m1["resources"][0]["pinned_digest"] == m1["resources"][0]["verified_digest"]
    kwargs["roles"] = [{"role": "Planner", "taxonomy_sha256": "3" * 64}]
    assert seed_hash(seed_manifest(seed, **kwargs)) != seed_hash(m1)


@pytest.mark.parametrize(
    "name", ["core", "core_test", "postgres", "core_unitd_xyz", "mydb"]
)
def test_isolated_database_name_defence(name: str) -> None:
    with pytest.raises(SeedError):
        validate_isolated_database_name(name)


def test_isolated_database_name_accepts_disposable_shape() -> None:
    validate_isolated_database_name("core_unitd_0123456789abcdef")
