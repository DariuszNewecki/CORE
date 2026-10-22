from __future__ import annotations

from will.workers.test_remediator._operations import failure_detail


# ID: 603320f3-71c8-43a1-8ecc-cfac92988942
def test_flow_step_error_beats_generic_reason():
    results = {
        "flow.build_test_for_symbol:0": {
            "ok": False,
            "data": {
                "error": "acceptance_rejected",
                "step_ref": "generate.test_snippet",
            },
        }
    }
    assert (
        failure_detail("Actions failed: flow.build_test_for_symbol:0", results)
        == "generate.test_snippet: acceptance_rejected"
    )


# ID: 1e1eaa3d-f0f6-45ae-8952-58513d6023d0
def test_details_still_win_over_error():
    results = {"a": {"data": {"error": "generic", "details": ["specific"]}}}
    assert failure_detail("reason", results) == "specific"


# ID: 207d5b3d-fca0-4f95-8094-18ad14802eda
def test_error_without_step_ref():
    assert failure_detail("reason", {"a": {"data": {"error": "boom"}}}) == "boom"
