#!/bin/sh
# Stop hook: a reply to the governor is at most 5 lines outside code blocks.
# The governor's standing rule ("outcome + decision, <=5 lines, no progress
# narration"), repeated for months as text, enforced here instead (L46).
exec python3 -I -c '
import json, sys
LIMIT = 5
event = json.load(sys.stdin)
if event.get("stop_hook_active"):
    sys.exit(0)  # one rewrite per reply; never loop
text = ""
try:
    with open(event["transcript_path"], encoding="utf-8") as fh:
        for raw in fh:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if entry.get("type") != "assistant":
                continue
            blocks = (entry.get("message") or {}).get("content") or []
            parts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
            if any(p.strip() for p in parts):
                text = "\n".join(parts)
except (OSError, KeyError):
    sys.exit(0)
lines, fenced = 0, False
for line in text.splitlines():
    if line.strip().startswith("```"):
        fenced = not fenced
        continue
    if not fenced and line.strip():
        lines += 1
if lines > LIMIT:
    print(json.dumps({"decision": "block", "reason": (
        f"Your reply has {lines} lines outside code blocks; the governor allows {LIMIT}. "
        "Rewrite it: the outcome in one line, then the one decision or action needed. "
        "No progress narration. Detail belongs in commits, ADRs or docs/.")}))
'
