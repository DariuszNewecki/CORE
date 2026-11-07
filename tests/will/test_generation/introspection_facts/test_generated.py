from __future__ import annotations

from unittest.mock import patch


# ID: 8836385b-bdf3-489d-bc81-56df774f7fc6
def test_build_introspection_facts():
    from will.test_generation.introspection_facts import build_introspection_facts

    # ID: 2ce201bf-de4a-4400-b19e-fe4121062843
    class DummyClass:
        def __init__(self, repo_root):
            self.repo_root = repo_root

        # ID: 0afb5d12-839d-4ad4-b900-602802ed5973
        def public_method(self):
            pass

        def _private_method(self):
            pass

    symbol_code = "class DummyClass:\n    pass\n"

    with patch(
        "will.test_generation.introspection_facts._import_target",
        return_value=DummyClass,
    ):
        facts = build_introspection_facts(
            file_path="src/body/services/foo.py",
            symbol_name="DummyClass",
            symbol_code=symbol_code,
        )

    assert facts["introspection_error"] is None
    assert facts["import_path"] == "body.services.foo"
    assert facts["kind"] == "class"
    assert facts["is_async"] is False
    assert "public_method" in facts["public_attrs"]
    assert "_private_method" in facts["private_attrs"]
    assert isinstance(facts["decorators"], list)
    assert isinstance(facts["awaited_call_sites"], list)
    assert facts["has_governance_decorator"] is False
