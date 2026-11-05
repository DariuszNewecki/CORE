from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from will.autonomy.proposal_consumer_effects import apply_success_effects


# ID: 4e133f8e-46c4-4c7f-b961-ae63728642a7
def test_apply_success_effects() -> None:
    worker = MagicMock()
    worker.post_artifact_finding = AsyncMock()

    result = {
        "action_results": {
            "action-1": {
                "ok": True,
                "data": {
                    "finding_to_post": {
                        "artifact_type": "python",
                        "sub_namespace": "test.result",
                        "identity_key_value": "src/foo.py",
                        "payload": {"detail": "x"},
                    }
                },
            },
            "action-2": {
                "ok": False,
                "data": {
                    "finding_to_post": {
                        "artifact_type": "python",
                        "sub_namespace": "test.result",
                        "identity_key_value": "src/bar.py",
                        "payload": {"detail": "y"},
                    }
                },
            },
        },
        "changed_files": ["src/pkg/module.py", "README.md", "src/pkg/data.txt"],
        "post_execution_sha": "abc123",
    }

    asyncio.run(apply_success_effects(worker, "proposal-42", result))

    assert worker.post_artifact_finding.await_count == 2
    worker.post_artifact_finding.assert_any_await(
        artifact_type="python",
        sub_namespace="test.result",
        identity_key_value="src/foo.py",
        payload={"detail": "x"},
    )
    worker.post_artifact_finding.assert_any_await(
        artifact_type="python",
        sub_namespace="test.coverage",
        identity_key_value="src/pkg/module.py",
        payload={
            "source_file": "src/pkg/module.py",
            "proposal_id": "proposal-42",
            "post_execution_sha": "abc123",
        },
    )
