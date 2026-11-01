from __future__ import annotations

from will.agents.prompt_model_iterative_agent import GenerationFailedError


# ID: 519bf7fe-f3e9-41c4-9641-66859ab63cfd
def test_GenerationFailedError():
    step_ref = "step-42"
    attempts = 3
    violations = ["missing docstring", "line too long"]
    reason = "budget_exhausted"

    error = GenerationFailedError(step_ref, attempts, violations, reason)

    assert error.step_ref == step_ref
    assert error.attempts == attempts
    assert error.violations == violations
    assert error.reason == reason
    assert isinstance(error, Exception)
    assert str(error) == (
        f"Generation failed for {step_ref!r} after {attempts} attempt(s): {reason}"
    )
