from __future__ import annotations

import pytest


# ID: 879457de-ef8d-46b3-aaf1-72342598e145
def test_run_as_script():
    with pytest.raises(ImportError):
        from will.tools.policy_vectorizer import run_as_script  # noqa: F401
