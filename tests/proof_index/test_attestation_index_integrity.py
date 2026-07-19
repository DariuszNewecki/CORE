# tests/proof_index/test_attestation_index_integrity.py
"""Integrity + freshness meta-check for .specs/attestations/proof-index.yaml (#798).

Runs without PostgreSQL. FAIL (blocking) on structural defects: malformed YAML,
unknown evidence mode, a referenced test file that does not exist, or an
incomplete attestation schema. Also FAIL (blocking, promoted 2026-07-19 now that
claims 4 and 6 are signed and no unattested live claim remains) on a missing or
stale attestation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_INDEX = _REPO_ROOT / ".specs/attestations/proof-index.yaml"
_VALID_MODES = {"ci-test", "attestation-only", "split"}
_ATTESTATION_FIELDS = {"reason", "status", "last_attested", "attested_by", "result"}


def _claims() -> list[dict]:
    return yaml.safe_load(_INDEX.read_text(encoding="utf-8"))["claims"]


def _referenced_tests(claim: dict) -> list[str]:
    if claim["evidence_mode"] == "ci-test":
        return claim.get("tests", [])
    if claim["evidence_mode"] == "split":
        return (claim.get("ci") or {}).get("tests", [])
    return []


def _attestation(claim: dict) -> dict | None:
    if claim["evidence_mode"] in ("attestation-only", "split"):
        return claim.get("attestation")
    return None


def test_index_wellformed_and_modes_valid() -> None:
    seen: set[int] = set()
    for c in _claims():
        assert "claim" in c and "evidence_mode" in c, c
        assert c["claim"] not in seen, f"duplicate claim {c['claim']}"
        seen.add(c["claim"])
        assert c["evidence_mode"] in _VALID_MODES, c


def test_referenced_tests_exist() -> None:
    for c in _claims():
        tests = _referenced_tests(c)
        if c["evidence_mode"] in ("ci-test", "split"):
            assert tests, f"claim {c['claim']}: {c['evidence_mode']} must declare tests"
        for t in tests:
            assert (_REPO_ROOT / t).exists(), f"claim {c['claim']}: missing referenced test {t}"


def test_attestation_schema_complete() -> None:
    for c in _claims():
        att = _attestation(c)
        if att is not None:
            missing = _ATTESTATION_FIELDS - set(att)
            assert not missing, f"claim {c['claim']}: attestation missing fields {missing}"


def test_no_missing_or_stale_attestations() -> None:
    # Blocking (promoted from warn 2026-07-19): every attestation-bearing claim
    # must be `attested` and within max_age. This is the forcing function that
    # makes an un-refreshed live claim a CI failure, not a silent gap.
    data = yaml.safe_load(_INDEX.read_text(encoding="utf-8"))
    max_age = int(data["meta"].get("default_attestation_max_age_days", 90))
    today = date.today()
    unattested: list[int] = []
    stale: list[tuple[int, int]] = []
    for c in data["claims"]:
        att = _attestation(c)
        if att is None:
            continue
        if att.get("status") != "attested":
            unattested.append(c["claim"])
            continue
        last = att.get("last_attested")
        assert last, f"claim {c['claim']}: attested but missing last_attested"
        last_date = last if isinstance(last, date) else date.fromisoformat(str(last))
        age = (today - last_date).days
        if age > max_age:
            stale.append((c["claim"], age))
    assert not unattested, f"live claims missing attestation: {unattested}"
    assert not stale, f"stale attestations (> {max_age}d): {stale}"
