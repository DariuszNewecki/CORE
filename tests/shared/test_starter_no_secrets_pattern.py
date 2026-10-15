"""starter.no_secrets matches prefixed names and short values (#1042).

Proof run 2: `DB_PASSWORD = "hunter2"` was not reported. `\\bpassword` cannot
match inside DB_PASSWORD (underscore is a word character) and the value had
7 characters where the pattern required 8.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
COPIES = (
    "packs/starter_python.yaml",
    "packs/python_hygiene.yaml",
    "src/shared/_packs/starter_python.yaml",
    "src/shared/_packs/python_hygiene.yaml",
)


def _pattern(rel: str) -> str:
    doc = yaml.safe_load((ROOT / rel).read_text())
    [pattern] = doc["enforcement_mappings"]["starter.no_secrets"]["params"][
        "forbidden_patterns"
    ]
    return pattern


# ID: 520f40e0-4828-40b4-a0aa-897bd1dea804
def test_every_copy_of_the_pack_uses_the_same_pattern() -> None:
    assert len({_pattern(rel) for rel in COPIES}) == 1


@pytest.mark.parametrize(
    "line",
    [
        'DB_PASSWORD = "hunter2"',  # the proof-run case
        'AWS_SECRET_KEY="abcd1234"',
        'api_key: str = "k-12345"',
        'GITHUB_ACCESS_TOKEN = "ghp_xxxx"',
        'self.client_secret = "abcdef"',
    ],
)
# ID: c9d8509e-0268-4033-946a-dafbba2e0159
def test_hardcoded_secrets_are_found(line: str) -> None:
    assert re.search(_pattern(COPIES[0]), line)


@pytest.mark.parametrize(
    "line",
    [
        'password = os.environ["DB_PASSWORD"]',
        'password = ""',
        'prompt = "Enter password: "',
        'token_type = "bearer"',
        "pwd = Path.cwd()",
    ],
)
# ID: bed41155-1a87-41e3-aff7-bb1bd55fd381
def test_lookups_prompts_and_empty_values_are_not(line: str) -> None:
    assert not re.search(_pattern(COPIES[0]), line)
