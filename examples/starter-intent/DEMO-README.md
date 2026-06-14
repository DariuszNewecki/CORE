# core-audit-demo

> Reference consumer for the
> [**CORE Constitutional Audit**](https://github.com/DariuszNewecki/CORE)
> GitHub Action.

This repository demonstrates, end to end, that the CORE audit gate works against
a real external repository: PR annotations land in the diff view and the action's
exit code can drive branch protection. It is the verification artifact for F-10.4
in the CORE roadmap.

> **This repo is generated.** Its `.intent/`, `src/`, and audit workflow are a
> published mirror of `examples/starter-intent/` in the
> [CORE repo](https://github.com/DariuszNewecki/CORE). Don't edit them here —
> edit the source of truth in CORE and run its `sync-to-demo.sh`.

## What the audit checks

A **minimal starter constitution** — four universal, deterministic (LLM-free)
rules, in plain language with none of CORE's internal vocabulary:

1. **`# ID:` anchors** on every public function/class — *blocking*.
2. **Docstrings** on public symbols — *reporting*.
3. **No `print()`** in importable code — *reporting*.
4. **No silently-swallowed exceptions** — *reporting*.

`src/hello.py` deliberately breaks all four, so the audit fails with one blocking
finding and annotates the offending lines. See
[`.intent/constitution/CONSTITUTION.md`](.intent/constitution/CONSTITUTION.md).

## Wire CORE into your own repo (5-minute quickstart)

1. Copy the contents of
   [`examples/starter-intent/.intent/`](https://github.com/DariuszNewecki/CORE/tree/main/examples/starter-intent)
   into your repository root. It is the smallest constitution that runs — not a
   copy of CORE's full ~250-file self-hosting ruleset.
2. Add `.github/workflows/audit.yml`:
   ```yaml
   name: Constitutional Audit
   on: [push, pull_request]
   jobs:
     audit:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: DariuszNewecki/CORE@main
           with:
             severity: block
   ```
3. (Optional) Require the **Constitutional Audit** check on your protected
   branches. Findings now block merge.

## Running the audit locally

```bash
pip install core-runtime
core-admin code audit --offline --format=text --severity=block
```

Exit codes: `0` no findings; `1` findings present; `2` configuration error;
`64` internal error (treat as gate failure).

## License

MIT. See [LICENSE](./LICENSE).
