from __future__ import annotations

from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError


# ID: 4ccbe482-46d4-48f4-91fb-98bfc6e38bee
def test_SafeAutoApprovalDeniedError():
    error = SafeAutoApprovalDeniedError(
        "proposal is not eligible", authorization_mode="enforce"
    )

    assert isinstance(error, Exception)
    assert str(error) == "proposal is not eligible"
    assert error.authorization_mode == "enforce"
    assert error.rule_id == "autonomy.proposals.safe_auto_approval_envelope"

    default_error = SafeAutoApprovalDeniedError("denied")
    assert default_error.authorization_mode is None
    assert default_error.rule_id == "autonomy.proposals.safe_auto_approval_envelope"
