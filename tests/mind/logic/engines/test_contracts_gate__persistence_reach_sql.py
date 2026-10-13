"""data.contracts.persistence_reach_coherence sees SQL writes.

The Worker blackboard publisher writes worker_uuid with raw SQL into the
BlackboardEntry table; the ORM class never appears next to post_* calls, so
the check reported a false positive every audit cycle (2026-10-13).
"""

from __future__ import annotations

from pathlib import Path

from mind.logic.engines.contracts_gate import _find_persistence_reach


_MODEL = """
class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = ({"schema": "core"},)
"""


def _tree(tmp_path: Path, publisher: str) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "models.py").write_text(_MODEL)
    (src / "publisher.py").write_text(publisher)
    return src


def test_write_method_inserting_into_the_table_reaches_the_class(
    tmp_path: Path,
) -> None:
    src = _tree(
        tmp_path,
        "class Pub:\n"
        "    async def post_report(self, subject):\n"
        "        return await self._post_entry(subject)\n\n"
        "    async def _post_entry(self, subject):\n"
        '        sql = "insert into core.entries (worker_uuid, subject) values (:w, :s)"\n'
        "        return sql\n",
    )
    assert _find_persistence_reach({"Entry"}, src) == {"Entry"}


def test_insert_into_another_table_does_not_reach_it(tmp_path: Path) -> None:
    src = _tree(
        tmp_path,
        "class Pub:\n"
        "    async def post_report(self, subject):\n"
        '        return "insert into core.other (worker_uuid) values (:w)"\n',
    )
    assert _find_persistence_reach({"Entry"}, src) == set()


def test_insert_outside_a_write_method_does_not_count(tmp_path: Path) -> None:
    src = _tree(
        tmp_path,
        "class Repo:\n"
        "    async def save(self):\n"
        '        return "insert into core.entries (worker_uuid) values (:w)"\n\n'
        "    async def post_report(self):\n"
        "        return None\n",
    )
    assert _find_persistence_reach({"Entry"}, src) == set()


def test_the_real_blackboard_publisher_reaches_blackboard_entry() -> None:
    src = Path(__file__).resolve().parents[4] / "src"
    assert "BlackboardEntry" in _find_persistence_reach({"BlackboardEntry"}, src)
