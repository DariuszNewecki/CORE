# src/body/governance/law_custody/__init__.py
"""
Law custody (ADR-170 Stage 1): ``core-admin law apply``.

A proposal under ``var/law-proposals/<id>/`` is read once into memory,
checked on a scratch tree by released code (data checks only -- the law's
custodian never runs repository code, ADR-170 D2), shown to the governor
with CORE's computed warnings and the proposer's declared ones, and on the
typed id written to every destination with one signed ledger line.

Modules:
- ``proposal``  -- read a proposal into memory (read-only).
- ``law_warnings`` -- D5 warnings computed from old and new bytes (pure).
- ``checks``    -- the scratch tree and the data checks run on it.
- ``ledger``    -- the D4 ledger line and its signature.
- ``writer``    -- the only code allowed to write governed text, and only
  as the custodian account.
"""

from __future__ import annotations
