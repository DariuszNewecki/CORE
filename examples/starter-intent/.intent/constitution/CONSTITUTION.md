# Starter Constitution

This is the smallest constitution that still does something real. It is meant to
be read in two minutes, copied into your own repository, and then grown.

A constitution is not a linter config. It is a short, human-readable statement of
what your code must be — declared once, as data, and enforced the same way on
every change by every author (human or AI). The CORE runtime reads the rules in
`.intent/rules/` and checks your code against them. Findings annotate the
offending lines in a pull request; blocking findings can stop a merge.

## What this starter enforces

Four rules, deliberately universal — they mean the same thing in any Python
project, carry none of CORE's internal vocabulary, and are all checked
deterministically (no language model, no network):

1. **No silent failures.** A bare `except:` (or `except Exception: pass`) hides
   the bug you most need to see. Name the exception and handle it. *(blocking)*
2. **Public symbols are documented.** A docstring states intent for anyone — or
   any tool — reading the code later. *(reporting)*
3. **Library code logs, it does not print.** `print()` in importable code is a
   debugging leftover; use a logger. *(reporting)*
4. **No hardcoded secrets.** Passwords, API keys and tokens assigned to string
   literals leak into version control; read them from the environment or a
   secrets manager. *(reporting)*

`blocking` rules fail the audit (non-zero exit, blocks merge under branch
protection). `reporting` rules surface as findings but do not fail the gate.

## How to grow it

Add a rule by adding an entry to `.intent/rules/starter.json` and a mapping in
`.intent/enforcement/mappings/starter.yaml` that points it at a check. The
machinery under `.intent/META/`, `.intent/taxonomies/`, and
`.intent/enforcement/config/` is CORE's — you should not need to edit it.
