from __future__ import annotations

from will.workers.test_remediator._operations import failure_detail


# ID: f76db76e-5e2a-4f9a-a50a-7d970b63aa2d
def test_failure_detail():
    execution_results = {
        "attempts": [
            {"status": "failed", "meta": {"details": ["specific error"]}},
        ],
    }
    assert failure_detail("generic reason", execution_results) == "specific error"
    assert failure_detail("generic reason", None) == "generic reason"
    assert failure_detail(None, {"other": []}) is None
