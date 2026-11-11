# Check a Record Against a Catalog

CORE can judge one structured record (a snapshot of a document library, already
resolved to one version per item) against a record catalog and print a verdict. It reads
two files and stores nothing: no database, no API, no web console.

**You need:** a pip-installed or checked-out CORE. No database or model is needed.

## Run it

```bash
core-admin record check snapshot.json --catalog publication_rules
```

`snapshot.json` is a record in format `library-snapshot/1`: an `items` object (id to
item), `known` (every id that exists), `scope` (null, or the ids to judge),
`load_findings` and `pre_findings`. The caller resolves the record and checks each item
against its type schema first; CORE judges what it is given (ADR-173).

`publication_rules` is the catalog of the 10 publication rules shipped with the
`publication_gate` engine.

## Reading the result

The text output gives the verdict and its evidence class, the record's SHA-256 (over its
RFC 8785 canonical form, so the verdict names exactly what it judged), one line per rule
(result and evidence class), and each finding under its rule, marked blocking or not.

| Exit code | Meaning |
|---|---|
| 0 | pass |
| 1 | fail: at least one blocking finding |
| 2 | undecided: only non-blocking findings, or a human must decide |
| 3 | the command could not run (unreadable record, unknown catalog, bad option) |

For example, a record that passes all 10 publication rules prints:

```text
Verdict: pass (proven)
Proven against the facts in this record; it does not vouch that they are true.
Record sha256: a08da1db238723b8d19db4ed93fc401a1e43983bf68e63044b20505b61070813
Catalog: publication_rules (10 rules)

Rules:
  publication.reference        pass       proven
  ...
  publication.authority        pass       proven

Findings: none
```

The second line says what the evidence class claims: how CORE reached the verdict on
the facts given (proven, judged by an AI reading, or not settled by CORE), never that the
record itself is true.

## JSON output

```bash
core-admin record check snapshot.json --catalog publication_rules --format json
```

prints the full verdict, format `record-verdict/1`: `format`, `outcome`,
`evidence_class`, `record_sha256`, `rule_ids` and `parts`. Each part has `rule_id`,
`engine_id`, `evidence_class`, `result` and `findings`; each finding has `rule`, `item`,
`message`, `blocking`, `carried` (true when the caller supplied it) and `details`. A new
field does not change the format name; a changed or removed one does.
