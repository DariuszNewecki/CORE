from __future__ import annotations

from will.autonomy.proposal_consumer_effects import summarize_flow_step_failures


# ID: 6fd92b2e-36a8-47d4-be50-e0f5f518a5f5
def test_summarize_flow_step_failures():
    action_results = {
        "flow:123": {
            "kind": "flow",
            "data": {
                "flow_id": "my_flow",
                "steps": [
                    {
                        "ref_id": "step_1",
                        "kind": "action",
                        "required": True,
                        "ok": True,
                        "data": {},
                    },
                    {
                        "ref_id": "step_2",
                        "kind": "action",
                        "required": False,
                        "ok": False,
                        "data": {"error": "Something went wrong"},
                    },
                    {
                        "ref_id": "step_3",
                        "kind": "action",
                        "required": False,
                        "ok": True,
                        "data": {},
                    },
                ],
            },
        },
    }

    result = summarize_flow_step_failures(action_results)

    assert len(result) == 1
    assert result[0] == {
        "flow_id": "my_flow",
        "step_ref_id": "step_2",
        "step_kind": "action",
        "step_error": "Something went wrong",
    }
