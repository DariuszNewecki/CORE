# Daily Loop (informal — not yet doctrine)

Status: working note. Not committed to `.intent/`.

1. **Pull down planning** — current band, open leads, parked items.
2. **State scan** — `core-admin code audit` (codebase violations), `core-admin runtime health` (workers, blackboard, crawls, blast radius), `core-admin runtime dashboard` (five-signal governor panel — convergence, inbox, loop, pipeline, reach), open GitHub issues. Two daemons must be up for the scan to be real: `core-daemon` (the worker loop) and `core-api` (FastAPI on :8000, which `code audit` calls). This determines the lead; don't pick before scanning.
3. **Choose one lead** — name it with an issue number. Park everything else.
4. **Ground the lead** — before producing anything, read the existing ADRs / papers / issues touching the lead's subject via `project_knowledge_search`. The scan says *what's open*; this says *what's already been decided*. Skipping it is how a "new" ADR duplicates an accepted one and a guessed number collides with a real one.
5. **Execute** — through Claude Code. Stop when the lead closes; don't chase adjacent threads.
6. **Update planning + file issues** — nothing parked informally. Deferred work gets an issue.
7. **Convergence check** — did this session close more than it opened? If findings are accumulating faster than they resolve, that's governance debt — flag it, don't bury it.
8. **Sync GitHub.**
9. **Post — only if earned** — to X / Dev.to *only* when the session produced something that stands on its own (an ADR, a closed gate, a working instrument). Not on a clock. Public sharing stays gated until CCC backlog converges.

---

**Why steps 2, 4, 7, 9 are non-negotiable:**

- **2 (scan before lead):** picking a goal from memory instead of current state is the recurring drift. The scan is the input to the decision, not a warm-up.
- **4 (ground the lead):** the scan finds open work but not its decision lineage. Producing against unread foundations is how effort duplicates accepted decisions. The repo is the authority and it's one search away — read it first.
- **7 (convergence):** the one system law a daily routine can quietly violate. Without an explicit check, the loop adds creation pressure (planning, posts) with no forcing function to close.
- **9 (post only if earned):** a daily posting obligation manufactures content regardless of substance. Honesty-led posting and a daily cadence are in tension — resolve it in favor of substance.
