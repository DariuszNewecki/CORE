# Constitution

This repository carries CORE's machinery: the files under `.intent/META/`,
`.intent/taxonomies/` and `.intent/enforcement/config/` that let the CORE runtime read
and enforce rules. It does not carry any rules yet. CORE does not choose a project's
law; you do.

A constitution is not a linter config. It is a short, human-readable statement of what
your code must be, declared once as data and enforced the same way on every change by
every author, human or AI. Rules live in `.intent/rules/`, and each one is pointed at a
check by a mapping in `.intent/enforcement/mappings/`. Findings annotate the offending
lines in a pull request; `blocking` rules fail the audit (non-zero exit, blocks merge
under branch protection), `reporting` rules surface findings without failing it.

## Until you add rules, the audit fails closed

`core-admin code audit` refuses to pass a repository with no declared rules: an audit
with nothing to check proves nothing.

## Add rules

Pick one:

- **Adopt a ready-made pack.** From the repository root:
  `core-admin project adopt-pack core/starter-python --write` adds four deterministic
  rules (no silently-swallowed exceptions, docstrings, no `print()` in library code, no
  hardcoded secrets). Other packs: `core/python-hygiene`, `core/architectural-boundaries`.
  Run it without `--write` first to preview.
- **Have rules proposed for your code.** `core project scout <path> --write` (from
  `pip install core-cli`, needs a running CORE API) reads your source, proposes rules
  that fit it, and asks you to ratify each one.
- **Write your own.** Add a rule document under `.intent/rules/` and a mapping under
  `.intent/enforcement/mappings/` that points it at a check.

Then run `core-admin code audit --offline` to see the findings.

The machinery files are CORE's. You should not need to edit them.

This file is yours: replace it with a statement of what your project's code must be.
