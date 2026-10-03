# Run a GRC Gap Analysis

CORE can check a folder of compliance documents — policies, procedures, records —
against a regulation's requirements catalog and report which requirements the documents
cover and which they do not.

**You need:** the full CORE runtime (PostgreSQL and Qdrant running — see
[Run the full runtime](getting-started.md)). An LLM is optional, but without one only the
deterministic requirements get a verdict (below).

## Run it

```bash
core-admin grc gap-analysis path/to/documents --catalog nist_800_171
```

CORE first judges whether the catalog applies to the documents at all. If they read as a
different domain, it asks before scoring (and, outside a terminal, stops without
scoring); an *uncertain* judgement warns and carries on. Pass `--assume-applicable` to
score regardless.

It then evaluates each requirement **across the whole folder**: a single document that
says nothing about a topic is not a gap, only a folder that never covers it is.

## Reading the report

Every row carries the **evidence class** of its verdict, so you always know how far to
trust it:

| Evidence | Established by | What it means |
|---|---|---|
| **proven** | a deterministic check | Mechanical and repeatable, e.g. no `TODO` or `DRAFT` left in a policy |
| **judged** | an AI reading of the text | Whether the documents address a requirement's substance |
| **attested** | a human | No automated method can settle it; the report says a person must |

Without an LLM configured, CORE does not guess: applicability is reported as
*uncertain* and judged requirements as *verdict unavailable*. Proven and attested rows
are unaffected.

## The catalogs

The public catalogs ship with `core-runtime`. Each is a **minimal subset** of its
regulation — enough to demonstrate the method, not a complete control set. The ones
marked published are:

| `--catalog` | Regulation |
|---|---|
| `nist_800_171` | NIST SP 800-171 Rev. 2 — protecting Controlled Unclassified Information |
| `cfr_part_11` | 21 CFR Part 11 — electronic records and signatures (FDA) |
| `eu_annex_11` | EU GMP Annex 11 — computerised systems |

Each catalog records its provenance and never reproduces copyrighted text. Catalogs
derived from licensed standards are not part of the open product; a deployment that is
entitled to them mounts them alongside the public ones, and they take precedence on a
name clash (ADR-116).

## Limits

- The report is evidence for a reviewer, not a compliance attestation.
- A *judged* verdict is an AI reading and can be wrong; treat it as a pointer to the
  document to check.
