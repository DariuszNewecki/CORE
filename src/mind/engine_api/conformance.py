# src/mind/engine_api/conformance.py

"""The public conformance checks for an engine class (ADR-177 D7).

``check_engine`` reads an engine class and lists every way it departs from
ADR-176: the D2 declarations, an unsupported ``api_version`` (D5(b), which the
registry refuses) and the D6 points (which 3.x only warns about). An empty
list means the class conforms. It builds nothing and runs nothing; CORE's own
built-in engines are held to the same checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from mind.logic.engines.contract import (
    api_version_problem,
    d6_problems,
    declaration_problems,
    engine_id_of,
)


@dataclass(frozen=True)
# ID: 8347c8ac-1599-4f79-9882-1a4eee2c3660
class ConformanceProblem:
    """One way an engine class departs from the contract: which rule, what."""

    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.message}"


# ID: 16c5e74d-e0c2-47f0-8e23-1ff01822b4ea
def check_engine(engine_cls: type) -> list[ConformanceProblem]:
    """Every contract problem of ``engine_cls``; empty when it conforms."""
    from mind.logic.engines import registry

    problems = [
        ConformanceProblem("ADR-176 D2", m) for m in declaration_problems(engine_cls)
    ]
    version = api_version_problem(engine_cls)
    if version is not None:
        problems.append(ConformanceProblem("ADR-176 D5(b)", version))
    default_id = engine_cls.__module__.rsplit(".", 1)[-1]
    engine_id = engine_id_of(engine_cls, default_id)
    problems += [
        ConformanceProblem("ADR-176 D6", m)
        for m in d6_problems(engine_cls, engine_id, registry.PASSIVE_ALIASES)
    ]
    return problems


__all__ = ["ConformanceProblem", "check_engine"]
