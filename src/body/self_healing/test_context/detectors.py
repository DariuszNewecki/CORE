# src/features/self_healing/test_context/detectors.py

"""Refactored logic for src/features/self_healing/test_context/detectors.py."""

from __future__ import annotations


# ID: 2ff96be2-ccfb-4ae2-8529-d5a30e5a919d
def analyze_dependencies(imports: list[str]) -> list[str]:
    return [
        i
        for i in imports
        if any(
            i.startswith(p) for p in ["core", "features", "shared", "services", "cli"]
        )
    ]


# ID: 58747330-67ea-4b4a-bf30-8b89816b8e49
def identify_external_deps(imports: list[str]) -> list[str]:
    patterns = [
        "httpx",
        "requests",
        "sqlalchemy",
        "psycopg2",
        "redis",
        "boto3",
        "anthropic",
        "openai",
    ]
    return list({i for i in imports for p in patterns if p in i.lower()})


# ID: 034392ba-2992-4514-b294-a479e66c70c9
def detect_fs_usage(code: str) -> bool:
    return any(
        x in code
        for x in [
            "Path(",
            "open(",
            ".read_text",
            ".write_text",
            ".mkdir(",
            ".exists(",
            "os.path",
            "shutil.",
        ]
    )


# ID: f338824d-8f2a-4a7b-b32f-ea6719278245
def detect_db_usage(code: str) -> bool:
    return any(
        x in code
        for x in [
            "get_session",
            "Session(",
            "query(",
            "select(",
            "insert(",
            "update(",
            "delete(",
            "sessionmaker",
        ]
    )


# ID: 8f68eb3c-155c-4c49-97e0-27681a52e29e
def detect_network_usage(code: str) -> bool:
    return any(
        x in code
        for x in ["httpx.", "requests.", "AsyncClient", ".get(", ".post(", "urllib."]
    )
