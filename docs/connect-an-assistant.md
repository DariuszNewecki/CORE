# Connect your AI assistant

Your coding assistant (Claude Code, Cursor, or any other that speaks MCP) can
ask CORE about your project instead of guessing, and check its own change
before it commits. CORE answers from your project's law and decision history,
with sources, and says plainly what it did not check.

The server runs locally, started by the assistant itself. It needs no
database, no API and no other service: `pip install core-runtime` is enough.

## What the assistant gets

| Tool | Question it answers |
|---|---|
| `law_rule` | What does this rule say, how is it enforced, and where is it declared? |
| `law_can_write` | May I write this path? What the law says, and what actually enforces it. |
| `decision_adr` | What did this architecture decision record (ADR) decide? |
| `decision_adrs` | Which ADRs exist (optionally only the accepted ones)? |
| `change_verdict` | Does my current change break a blocking rule? |

Every tool only reads. None can approve, waive, or act as the governor.

The same answers are available from the shell, which is the quickest way to
see what the assistant will see:

```bash
core-admin law show governance.constitution.read_only
core-admin law check .intent/rules/example.json
core-admin decisions list --status accepted
core-admin code verify
```

## What you need

- `core-runtime` installed (`pip install core-runtime`), so `core-admin` is on
  your `PATH`.
- A project with a `.intent/` directory. To start one, see
  [Start a governed project](start-a-project.md) or
  [Add a rule pack](adopt-a-pack.md).

## Claude Code

From your project's root:

```bash
claude mcp add --scope project core -- core-admin mcp run
```

This writes a `.mcp.json` file at the project root; commit it, so everyone
who works on the repository gets the same setup:

```json
{
  "mcpServers": {
    "core": {
      "type": "stdio",
      "command": "core-admin",
      "args": ["mcp", "run"]
    }
  }
}
```

The next time you start `claude` in the project, it asks once whether to
trust the `core` server. That approval is yours to give; `claude mcp list`
shows the server as pending until you do. To use it only yourself, leave out
`--scope project`: Claude Code then keeps the entry in your own settings.

## Other assistants

Any MCP client can start the server over stdio. Configure:

- **command:** `core-admin`
- **arguments:** `mcp run --repo /path/to/your/project`

`--repo` names the project to serve. Without it, the server serves the project
around its working directory, which is enough for assistants that start it in
the project root.

## What the answers mean

- **Sources and limits.** Every law and decision answer names the files it
  came from and states what it does not establish. A rule or ADR that does
  not exist is answered as *unknown*, never guessed.
- **The verdict is feedback, not a pass.** `change_verdict` judges the
  changed files against the per-file rules and answers `BLOCKED`,
  `CLEAR_IN_SCOPE`, `NO_CHANGES` or `NOT_EVALUATED` (nothing could be judged,
  for example a project with no rules yet). It lists every rule it did not
  evaluate, such as whole-repository checks. It never says PASS: only the full
  audit (`core-admin code audit`, in your commit hook or CI) does.
- **Detected, not prevented.** CORE does not stop an assistant from editing
  files directly. `law_can_write` says so for protected paths: CORE refuses
  such writes on its own write path and detects them in every audit, and a
  protected branch with required checks keeps them from landing.
