# tests/test_env_loading.py
"""
A diagnostic test to isolate and verify that pytest-dotenv is working.
This test has NO imports from the 'src' directory to avoid interference.
"""

import os


def test_database_url_is_loaded_by_pytest_dotenv():
    """
    This test will only pass if the pytest-dotenv plugin is correctly
    finding, parsing, and loading the .env.test file.
    """
    assert (
        "DATABASE_URL" in os.environ
    ), "pytest-dotenv failed to load DATABASE_URL from .env.test"
    assert (
        "testdb" in os.environ["DATABASE_URL"]
    ), "The loaded DATABASE_URL does not seem to be the correct test URL."
