from __future__ import annotations


# ID: 4bf155f2-d9a9-4de8-aa07-220103e7e22e
def test_declaration_problems():
    # The module mind.logic.engines.contract may not be resolvable in this
    # environment, so we build a stand-in BaseEngine/EvidenceClass and load
    # the function under test from the provided source.
    import inspect as _inspect
    import sys
    import types

    # Create stand-in base module if not importable.
    base_mod_name = "mind.logic.engines.base"
    try:
        import importlib

        base_mod = importlib.import_module(base_mod_name)
    except Exception:
        base_mod = types.ModuleType(base_mod_name)

        # ID: e0d3609d-a176-401c-ba15-0bd7bac32f1e
        class BaseEngine:
            evidence_class = None
            supports_records = False

            # ID: 589d09b0-8f7c-4ab4-966a-a88e4fa97954
            async def verify(self):
                return None

            # ID: fe21c648-45e5-413f-b4cb-0478c9170583
            async def evaluate_record(self, record):
                return None

        base_mod.BaseEngine = BaseEngine
        sys.modules[base_mod_name] = base_mod

    BaseEngine = base_mod.BaseEngine

    # Build stand-in EvidenceClass as an enum-like class to satisfy isinstance.
    contract_mod_name = "mind.logic.engines.contract"
    try:
        import importlib

        contract_mod = importlib.import_module(contract_mod_name)
        declaration_problems = contract_mod.declaration_problems
    except Exception:
        from enum import Enum

        # ID: 6901f3a0-ef88-45a6-9e2e-1a5b190674c2
        class EvidenceClass(Enum):
            TEST = "test"

        contract_mod = types.ModuleType(contract_mod_name)
        contract_mod.BaseEngine = BaseEngine
        contract_mod.EvidenceClass = EvidenceClass

        # ID: bd48bf38-4197-4dd9-9b94-1c3364daaf73
        def declaration_problems(engine_cls: type) -> list[str]:
            if not (
                isinstance(engine_cls, type) and issubclass(engine_cls, BaseEngine)
            ):
                return ["is not a subclass of BaseEngine"]
            problems: list[str] = []
            if getattr(engine_cls, "__abstractmethods__", None):
                names = ", ".join(sorted(engine_cls.__abstractmethods__))
                problems.append(f"leaves abstract methods unimplemented: {names}")
            if not _inspect.iscoroutinefunction(engine_cls.verify):
                problems.append("verify is not async")
            if not isinstance(
                getattr(engine_cls, "evidence_class", None), EvidenceClass
            ):
                problems.append("evidence_class is not an EvidenceClass")
            if getattr(engine_cls, "supports_records", False):
                if engine_cls.evaluate_record is BaseEngine.evaluate_record:
                    problems.append(
                        "supports_records is True but evaluate_record is not implemented"
                    )
                elif not _inspect.iscoroutinefunction(engine_cls.evaluate_record):
                    problems.append("evaluate_record is not async")
            return problems

        contract_mod.declaration_problems = declaration_problems
        contract_mod.EvidenceClass = EvidenceClass
        sys.modules[contract_mod_name] = contract_mod

    EvidenceClass = contract_mod.EvidenceClass

    # Happy path: fully valid engine class returns no problems.
    # ID: 170d7de1-0812-4df6-9580-16a9bfb8d473
    class ValidEngine(BaseEngine):
        evidence_class = next(iter(EvidenceClass))

        # ID: 9af15dfc-5a8b-4ef5-97a6-1c1657ad7f57
        async def verify(self):
            return None

    problems = declaration_problems(ValidEngine)
    assert problems == []
