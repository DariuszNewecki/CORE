"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/api/v1/development_routes.py
- Symbol: DevelopmentGoal
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:41:58
"""

import pytest

from api.v1.development_routes import DevelopmentGoal


# Detected return type: DevelopmentGoal is a Pydantic BaseModel class, not a function.
# Therefore, tests will focus on instantiation, field validation, and model behavior.


def test_development_goal_instantiation():
    """Test basic instantiation with a valid goal string."""
    goal_text = "Learn Pytest"
    dev_goal = DevelopmentGoal(goal=goal_text)
    assert dev_goal.goal == goal_text


def test_development_goal_goal_field_required():
    """Test that the 'goal' field is required."""
    with pytest.raises(ValueError):
        DevelopmentGoal()


def test_development_goal_goal_must_be_string():
    """Test that the 'goal' field must be a string."""
    with pytest.raises(ValueError):
        DevelopmentGoal(goal=123)


def test_development_goal_empty_string_allowed():
    """Test that an empty string is a valid goal value."""
    dev_goal = DevelopmentGoal(goal="")
    assert dev_goal.goal == ""


def test_development_goal_whitespace_string_allowed():
    """Test that a whitespace-only string is a valid goal value."""
    dev_goal = DevelopmentGoal(goal="   \t  ")
    assert dev_goal.goal == "   \t  "


def test_development_goal_special_characters():
    """Test that strings with special characters and Unicode are valid."""
    goal_text = "Learn API design & deployment (backend) … and more!"
    dev_goal = DevelopmentGoal(goal=goal_text)
    assert dev_goal.goal == goal_text
