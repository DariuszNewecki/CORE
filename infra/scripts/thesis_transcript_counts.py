"""Write the thesis measure's transcript trip counts, numbers only (#1396).

Governor 2026-11-01: the daemon (user core) gets no read access to
/home/core-claude. Instead this job, run from core-claude's crontab with the
live release's Python, counts the round trips in core-claude's Claude Code
transcripts per day and writes only those counts to a file core can read
(group core-dev, mode 0640). The thesis measure reads that file.

    crontab: 30 5 * * * live=$(basename "$(readlink -f /opt/core/current)") && git -C /opt/dev/CORE show "$live:infra/scripts/thesis_transcript_counts.py" | /opt/core/current/venv/bin/python -I - >> "$HOME/.cache/thesis-transcript-counts.log" 2>&1

CORE_CLAUDE_TRANSCRIPTS and CORE_THESIS_TRIP_COUNTS override the paths. The
counting is the measure's own (body.services.thesis.measure), not a copy.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from body.services.thesis.measure import LONG_WINDOW, trip_counts_payload


TRANSCRIPTS = Path(
    os.environ.get(
        "CORE_CLAUDE_TRANSCRIPTS", "/home/core-claude/.claude/projects/-opt-dev-CORE"
    )
)
OUT = Path(
    os.environ.get(
        "CORE_THESIS_TRIP_COUNTS", "/opt/dev/CORE/var/thesis/transcript_trips.json"
    )
)


def write(payload: dict, out: Path) -> None:
    """Atomic, group-readable (0640), never world-readable."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    with os.fdopen(fd, "w") as handle:
        json.dump(payload, handle, sort_keys=True)
    os.chmod(tmp, 0o640)
    os.replace(tmp, out)


def main() -> int:
    now = datetime.now(UTC)
    if not TRANSCRIPTS.is_dir():
        print(
            f"{now.isoformat()} transcripts not found: {TRANSCRIPTS}", file=sys.stderr
        )
        return 1
    since = (now - LONG_WINDOW).date()
    payload = trip_counts_payload(TRANSCRIPTS, since, now)
    write(payload, OUT)
    total = sum(sum(day.values()) for day in payload["days"].values())
    print(f"{now.isoformat()} wrote {OUT}: {len(payload['days'])} days, {total} trips")
    return 0


if __name__ == "__main__":
    sys.exit(main())
