# src/features/test_generation_v2/harness_detection.py

"""
Harness Detection

Purpose:
- Detect whether the repo appears to have an available database/integration test harness.
- This is a heuristic gate used to decide whether integration-style tests are permissible.

Design:
- Conservative by default: "no harness" unless we find strong signals.
- Pure, deterministic checks against repository files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
# ID: 2d1f5f63-6b63-4b36-a4b1-1f4c8a52a04d
class HarnessSignals:
    has_tests_conftest: bool
    has_pytest_postgresql_signals: bool
    has_sqlalchemy_fixture_signals: bool
    notes: list[str]

    @property
    # ID: 5c194801-186c-4709-bc88-c766b81733c3
    def has_db_harness(self) -> bool:
        # Strict: require strong evidence. Either pytest-postgresql-like signals
        # or project-local SQLAlchemy fixtures.
        return self.has_pytest_postgresql_signals or self.has_sqlalchemy_fixture_signals


# ID: 21d8c8b6-8b0f-4a7d-9b65-9b2eacb4f0d1
class HarnessDetector:
    """Heuristic harness detector for integration-capable tests."""

    def __init__(self, repo_root: Path):
        self._repo_root = repo_root

    # ID: b45db7b5-a3f4-4541-8d54-5e0e7add2cc3
    def detect(self) -> HarnessSignals:
        notes: list[str] = []

        conftest = self._repo_root / "tests" / "conftest.py"
        has_tests_conftest = conftest.exists()
        if has_tests_conftest:
            notes.append("Found tests/conftest.py")
            content = self._safe_read(conftest)
        else:
            content = ""

        # Signals suggesting pytest-postgresql / process-based postgres fixture usage.
        # (Your failure indicates postgresql_proc isn't available; we treat that as absent unless explicitly found.)
        pytest_postgresql_tokens = [
            "postgresql_proc",
            "postgresql_engine",
            "pytest_postgresql",
        ]
        has_pytest_postgresql_signals = any(
            tok in content for tok in pytest_postgresql_tokens
        )
        if has_pytest_postgresql_signals:
            notes.append(
                "Detected pytest-postgresql-style fixture tokens in tests/conftest.py"
            )

        # Signals suggesting a project-local SQLAlchemy fixture harness.
        sqlalchemy_fixture_tokens = [
            "engine",
            "session",
            "Session",
            "async_session",
            "AsyncSession",
            "sqlalchemy",
            "create_engine",
            "create_async_engine",
            "sessionmaker",
            "async_sessionmaker",
        ]
        # Require at least a couple tokens to avoid false positives.
        sqlalchemy_hits = sum(1 for tok in sqlalchemy_fixture_tokens if tok in content)
        has_sqlalchemy_fixture_signals = sqlalchemy_hits >= 3
        if has_sqlalchemy_fixture_signals:
            notes.append(
                "Detected project-local SQLAlchemy fixture signals in tests/conftest.py"
            )

        return HarnessSignals(
            has_tests_conftest=has_tests_conftest,
            has_pytest_postgresql_signals=has_pytest_postgresql_signals,
            has_sqlalchemy_fixture_signals=has_sqlalchemy_fixture_signals,
            notes=notes,
        )

    def _safe_read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
