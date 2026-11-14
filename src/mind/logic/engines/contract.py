# src/mind/logic/engines/contract.py

"""What ADR-176 asks of an engine class, as plain checks.

One source for the registry (which warns or refuses at load) and for the
public conformance suite (``mind.engine_api.conformance``, ADR-177 D7). Each
check reads the class only: it builds nothing and runs nothing.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Iterable

from .base import CORE_ENGINE_API, BaseEngine, EvidenceClass


# ADR-176 D2: the services CORE injects, and the engine_id format.
INJECTED_SERVICES = frozenset({"path_resolver", "llm_client", "embedding_client"})
_ENGINE_ID_FORMAT = re.compile(r"^[a-z0-9_]+$")


# ID: c402433f-f874-4a20-9798-082c23735c2d
def engine_id_of(engine_cls: type, default_id: str) -> str:
    """The id the registry files the class under: its ``engine_id``, else
    ``default_id`` (the module name, for a class that declares none)."""
    return getattr(engine_cls, "engine_id", default_id)


# ID: b6d7db3d-14b0-4fd2-ab95-05e04f0245c3
def api_version_problem(engine_cls: type) -> str | None:
    """ADR-176 D5(b): why the class's ``api_version`` is not supported, or None."""
    api_version = str(getattr(engine_cls, "api_version", "1"))
    if api_version.split(".")[0] != CORE_ENGINE_API:
        return f"declares api_version {api_version!r}; this CORE supports {CORE_ENGINE_API!r}"
    return None


# ID: a4ffac9b-da9a-4aeb-917c-d3ae9024808f
def d6_problems(
    engine_cls: type, engine_id: str, passive_aliases: Iterable[str]
) -> list[str]:
    """What the class does against ADR-176 D2 that 3.x only warns about (D6)."""
    problems: list[str] = []
    if "engine_id" not in vars(engine_cls):
        problems.append("no explicit engine_id on the class")
    if not _ENGINE_ID_FORMAT.match(engine_id):
        problems.append(
            f"engine_id {engine_id!r} is not lowercase letters, digits and underscores"
        )
    if engine_id in set(passive_aliases):
        problems.append(f"engine_id {engine_id!r} is also a passive alias")
    unknown = sorted(required_constructor_params(engine_cls) - INJECTED_SERVICES)
    if unknown:
        problems.append(
            f"constructor requires {', '.join(unknown)}, which CORE does not inject"
        )
    return problems


# ID: b73538e2-2c07-4e81-9e97-50ed04e0ffcd
def required_constructor_params(engine_cls: type) -> frozenset[str]:
    """Constructor parameters without a default (``*args``/``**kwargs`` excluded)."""
    try:
        params = list(inspect.signature(engine_cls.__init__).parameters.items())  # type: ignore[misc]
    except (TypeError, ValueError):
        return frozenset()
    return frozenset(
        name
        for name, param in params
        if name != "self"
        and param.kind
        not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        and param.default is inspect.Parameter.empty
    )


# ID: f9c1cda0-5777-4063-99dc-48d12d1040ae
def declaration_problems(engine_cls: type) -> list[str]:
    """ADR-176 D2 declarations the registry does not check at load: the class
    is a ``BaseEngine``, ``verify`` is async, ``evidence_class`` is an
    ``EvidenceClass``, and a record engine has its own async ``evaluate_record``."""
    if not (isinstance(engine_cls, type) and issubclass(engine_cls, BaseEngine)):
        return ["is not a subclass of BaseEngine"]
    problems: list[str] = []
    if getattr(engine_cls, "__abstractmethods__", None):
        names = ", ".join(sorted(engine_cls.__abstractmethods__))
        problems.append(f"leaves abstract methods unimplemented: {names}")
    if not inspect.iscoroutinefunction(engine_cls.verify):
        problems.append("verify is not async")
    if not isinstance(getattr(engine_cls, "evidence_class", None), EvidenceClass):
        problems.append("evidence_class is not an EvidenceClass")
    if getattr(engine_cls, "supports_records", False):
        if engine_cls.evaluate_record is BaseEngine.evaluate_record:
            problems.append(
                "supports_records is True but evaluate_record is not implemented"
            )
        elif not inspect.iscoroutinefunction(engine_cls.evaluate_record):
            problems.append("evaluate_record is not async")
    return problems
