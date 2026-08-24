# GRC synthetic test corpus (`synthetic_corpus/`)

Fully synthetic governance documents used as a realistic corpus for the GRC
gap-analysis engine (`grc_judge` + the deterministic lanes). They exercise the
full honesty spectrum against the default `nist_800_171` catalog.

This note lives **outside** `synthetic_corpus/` on purpose: the engine scans
every `.md`/`.txt` in the corpus directory, so the corpus must contain only
documents-under-test — a meta-file with placeholder words (TBD/DRAFT/TODO)
would itself be flagged as an unfinalized document.

| Document | Expected lane outcome |
|---|---|
| `remote-access-policy.md` | **proven → GAP** — retains `TBD` / `DRAFT` placeholders → trips the "finalized" `regex_gate` |
| `information-security-baseline.md` | finalized (proven met); addresses authorized-access (3.1.1), MFA (3.5.3), risk assessment (3.11.1), and system security plan (3.12.4) topics |

Verified empirically with no LLM wired: `doc_finalized` → proven gap (anchored on
`remote-access-policy.md`), judged lanes → `pending_ai`, attested lanes → `needs_human`.

## Provenance

These documents are **entirely synthetic**: written directly from the
`nist_800_171` catalog's own requirement statements
(`grc-catalogs/public/nist_800_171/catalog.yaml`), not derived from, modeled
on, or containing any excerpt of a real organization's governance material.
They carry no lineage to any third-party or employer document. Any
resemblance to a real policy's structure (owner line, review cadence,
numbered sections) is coincidental — that shape is the generic form of a
governance document, not copied from a specific source.
