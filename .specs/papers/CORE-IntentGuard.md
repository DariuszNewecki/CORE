<!-- path: .specs/papers/CORE-IntentGuard.md -->

# CORE — IntentGuard

**Status:** Canonical
**Authority:** Constitution
**Scope:** All file writes in CORE

---

## 1. Purpose

This paper defines IntentGuard — the runtime Gate that evaluates every
file write against constitutional Rules before it happens.

---

## 2. Definition

IntentGuard is invoked automatically on every call to
`FileHandler.write_runtime_text()`. It cannot be bypassed. A write that
does not pass IntentGuard does not happen.

IntentGuard evaluates the target path and content against the
constitutional rules applicable to that file's architectural layer.
If any blocking rule is violated, it raises `ValueError` with the
violation message. The write is aborted.

---

## 3. Invocation Point

IntentGuard is called at `FileHandler._guard_paths()`, which is invoked
by `write_runtime_text()` before any disk operation occurs.

Every file write in CORE goes through `FileHandler`. There is no
alternative write path that bypasses IntentGuard.

---

## 4. What It Evaluates

IntentGuard evaluates:

**Path boundaries** — certain paths are constitutionally forbidden:
- `.intent/` — the Constitution is immutable to CORE at runtime
- `var/keys/` — secret storage
- `var/cache/` — ephemeral cache
- Absolute paths — forbidden unconditionally
- Path traversal (`..`) — forbidden unconditionally

**Constitutional rules** — rules applicable to the target file's layer
are evaluated against the proposed content. If any blocking rule
(enforcement: blocking) is violated, the write is rejected.

Layer is determined by the file path:
- `src/will/` → Will layer
- `src/body/` → Body layer
- `src/mind/` → Mind layer
- `src/shared/` → Shared layer
- `src/cli/` → CLI layer

---

## 5. Strict vs Non-Strict Mode

IntentGuard operates in two modes:

**Strict mode** — blocking rules and policy rules both prevent the write.
**Non-strict mode** (default) — only blocking rules (enforcement: blocking)
prevent the write. Reporting and advisory rules are noted but do not block.

### 5a. Mode Selection

Mode is selected at IntentGuard construction time and is system-wide
for the lifetime of the process. It is not configurable per-action,
per-Worker, or per-Proposal.

The mode is set by the component that constructs the IntentGuard instance:

- **Daemon startup** — the daemon constructs IntentGuard in non-strict
  mode (default). All autonomous Workers operate under non-strict mode.
- **CLI commands that explicitly request strict validation** — may
  construct IntentGuard with `strict=True`. This is declared at the
  CLI command level, not by the Worker or action.
- **Tests** — may construct IntentGuard in either mode as required.

No Worker, AtomicAction, or Proposal may select or override the mode
at runtime. Mode selection is a startup-time declaration, not a
per-write decision.

---

## 6. Initialization

IntentGuard is initialized with the full rule set at startup:

```
IntentGuard initialised: N constitutional rules (always-block) + M policy
rules (advisory). Strict mode: False.
```

Constitutional rules (Authority: Constitution) always block regardless
of mode. Policy rules (Authority: Policy) block only in strict mode.

---

## 7. Failure Response

When IntentGuard blocks a write it raises:

```
ValueError: Blocked by IntentGuard: {violation message}
```

The caller receives this exception. No partial write occurs.
The violation message contains the specific rule that was violated.

---

## 8. Non-Goals

This paper does not define:
- the specific rules IntentGuard enforces
- how rules are declared in `.intent/rules/`
- the FileHandler implementation
