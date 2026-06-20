# GRC governance test corpus (`governance_corpus/`)

Neutralized governance documents used as a realistic corpus for the GRC
gap-analysis engine (`grc_judge` + the deterministic lanes). They exercise the
full honesty spectrum against the default `nist_800_171` catalog.

This note lives **outside** `governance_corpus/` on purpose: the engine scans
every `.md`/`.txt` in the corpus directory, so the corpus must contain only
documents-under-test — a meta-file with placeholder words (TBD/DRAFT/TODO)
would itself be flagged as an unfinalized document.

| Document | Expected lane outcome |
|---|---|
| `enterprise-patching-policy.md` | **proven → GAP** — retains `TBD` / `DRAFT` placeholders → trips the "finalized" `regex_gate` |
| `access-review-work-instruction.md` | **judged → MET** on authorized-access (3.1.1); **gap** on MFA (3.5.3) |
| `itam-governance-charter.md` | finalized (proven met); **judged partial** on access; exercises the **needs-human** attestation lane |

Verified empirically with no LLM wired: `doc_finalized` → proven gap (anchored on
the patching policy), judged lanes → `pending_ai`, attested lanes → `needs_human`.

## Provenance & neutralization

These are **derivatives of the repository owner's own authored work**, deliberately
neutralized so they carry **no third-party or customer identifiers**, and verified
clean by the repository owner before commit. Removed or generalized: organization /
entity names, author names, office / address details, internal audit reference
numbers, internal document codes, named internal tools, and jurisdiction-specific
tells. Standard framework names (NIS2, GDPR, ISO/IEC 19770-1, ISO/IEC 27001, ITIL)
are retained — industry-standard, non-identifying, and they keep the corpus
realistic for the judge.
