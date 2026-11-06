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


from unittest.mock import patch

from will.autonomy.safe_auto_approval_envelope import validate_envelope


# ID: fcc29ab2-d00f-43e3-8fb8-ac8f2aee12dd
def test_validate_envelope() -> None:
    envelope = {
        "authorization_mode": "allow_listed",
        "authorized_actions": frozenset({"edit"}),
        "authorized_path_prefixes": ("src/",),
        "authorized_extensions": (".py",),
    }
    actions = [
        {
            "action_id": "edit",
            "parameters": {"file_path": "src/foo.py"},
        }
    ]
    scope = {"files": ["src/foo.py"]}

    with (
        patch(
            "will.autonomy.safe_auto_approval_envelope.load_safe_auto_approval_envelope",
            return_value=envelope,
        ),
        patch(
            "will.autonomy.safe_auto_approval_envelope._validate_target_path",
        ) as mock_validate_path,
    ):
        assert validate_envelope(actions, scope) is None
        mock_validate_path.assert_called_once_with("src/foo.py", ("src/",), (".py",))
