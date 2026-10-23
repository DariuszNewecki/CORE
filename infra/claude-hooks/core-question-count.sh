#!/bin/sh
# Stop hook (#1307): one line, the UTC time, in ~/.cache/governor-questions.log
# for each final reply that ends with "?". Counts questions to the governor;
# never blocks. A rewrite forced by another Stop hook is not counted twice.
exec python3 -I -c '
import json, os, sys, datetime
event = json.load(sys.stdin)
if event.get("stop_hook_active"):
    sys.exit(0)
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
if text.rstrip().endswith("?"):
    log = os.path.expanduser("~/.cache/governor-questions.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
'
