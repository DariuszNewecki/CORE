# ADR-159 Trial 0 — Result Attestation (2026-09-18)

**Status:** Trial result record. Filed under `.specs/attestations/` per ADR-159 D5/D9 and the Trial 0
Apparatus Design §7 amendment (custody procedure step 7). This file records the single governed
invocation of Trial 0, its terminal outcome, and the integrity of the retained evidence. It
contains no raw evidence, no sealed content and no credentials.

**Ruling reference:** `.specs/decisions/ADR-159-autonomy-thesis-acceptance-boundary.md`, Note
*2026-09-18 — Governor ruling: Trial 0 result recorded — FAIL-before-bootstrap (apparatus boundary)*.

**Verdict: FAIL-before-bootstrap — apparatus boundary. No retry is authorized.**

---

## 1. Pins and frozen inputs

| item | value |
|---|---|
| Control repository at invocation | `64c83daaf99b53f4b5140a7e9e509138ead89b7d` (clean, = `origin/main`, CI green) |
| Runner (certified, ADR-159 Note 2026-09-18) | commit `c0ccd6ce9f57f457e20c06612fc7d43067b09481`, tree `198659de31f8ab70c404210d8ead0c9bdb870d0d`; fresh clone, worktree content hash `66f86092d4774bfba68115ccea3f3ac17de45f8766982cbbb59cd3ffc598aab0` (identical pre/post) |
| Subject (frozen CORE, D5) | commit `c4d9fdf9dc52c7d71981e367b64d00b0c994910b`, tree `76da78a7afb640cf5cac359510aa405ff7a1ce3d`; fresh clone, immutable, worktree content hash `b41ad8f504a1c601cd61291e6b64f943b848addc0eab5eef3979b27244f8e4f1` (identical pre/post) |
| Frozen launcher (`trial0-launch.sh`, 5846 bytes) | `48e92536ce8ee1caca44d94a99c9bb10593d6ed1f33b4317b8cf2ae7d536f7f3` — unchanged before, during and after |
| Frozen task statement (#895 certified text, 194 bytes, no trailing newline) | `0b948f4db78dd8c67469b5c3ae47342e32062ad6ff3d3e17080175c9e4fe950f` |
| Staged inputs (`SHA256SUMS`, 12 files, = `.specs/planning/adr-159-trial0-apparatus/`) | `ed83b746b24d45faa42d742bdbc9bf00cc33a4b9294667d1ac10338dd4c29670`, 12/12 OK at launch |
| Amended coldroom readiness report (authoritative) | `3a5666a678f3065904d508344d1128a2450b7d683fa2f673dbf42d78e4f0440e` |

## 2. Invocation and terminal outcome

| item | value |
|---|---|
| Invocation (UTC) | **2026-09-18T17:39:44Z** (operator clock); launcher start stamp `20260918T173945Z` (coldroom clock, 1 s skew) |
| Invoked as | unprivileged `runner` (uid 1001, no sudo, no capabilities), by `sudo -u runner -H <launcher>`; exactly one invocation in the coldroom's sudo journal |
| Runner exit code | **64** (`EXIT_INTERNAL_FAILURE`), same second as invocation |
| Runner stderr (complete) | `INTERNAL FAILURE — PermissionError: [Errno 13] Permission denied: '/home/ops/.intent'` |
| Runner stdout | empty |
| Launcher exit | 0 (recorded hashes pre/post, froze the run directory) |
| Governed run created | **none** — no `runs/` directory, no `binding.json`, no `refusal.json`, no `outcome.json`, no Blackboard row, no export, no recall figure |
| Interventions, retries | none |

**Mechanism.** The launcher does not set a working directory; `sudo` preserved the operator's
cwd, the `ops` login home (mode 750), which `runner` cannot traverse. At `c0ccd6ce`,
`src/shared/config.py` resolves default paths by walking up from `Path.cwd()` and testing
`(candidate / ".intent").is_dir()`; `is_dir()` swallows ENOENT but re-raises EACCES. The first
`shared` import on the external-run path (step 2b, after the stdlib-only subject and evidence-root
checks and before any directory is created) constructs `Settings()`, whose `default_factory`
fields run that walk, raise `PermissionError`, and `runtime_external_run.run()` converts the
exception to exit 64. The runner therefore never bound the target, seeded, planned, or wrote.

## 3. Failure boundary — apparatus

- **Apparatus:** the frozen launcher did not pin an explicit, accessible working directory, and
  the documented invocation path (from the `ops` login shell) inherits an untraversable one.
- **Not the runner's governed path:** the runner touched neither subject nor database nor
  network, produced no wrong evidence and violated no boundary; its cwd-walk is documented
  behaviour (#544/#545) that the #895 certification exercised only from a readable cwd.
- **Backlog observation (not the assigned cause):** the runner treats an unreadable ancestor
  directory during cwd discovery as fatal rather than skipping it. Recorded for later triage; no
  issue created by this attestation. The nearest existing issue on cwd-walk root resolution is
  #892 (a different symptom).

## 4. Integrity of the apparatus and state (verified pre- and post-invocation)

| property | result |
|---|---|
| Subject read-only | held — every file immutable, 0 write bits, hash identical pre/post |
| Runner checkout | unchanged — hash identical pre/post |
| Disposable database | logically unchanged — 98 `core` tables, 0 inserted/updated/deleted/live tuples, `llm_resources` 0 rows |
| Network containment | held — 16/16 socket probes (3 allowed-path checks, 13 denied targets) as `runner` immediately before invocation; guest and hypervisor-side rule sets unchanged |
| Seal | never opened, copied or referenced beyond its digest; absent from the coldroom, the CORE host and this bundle |

**Database schema hash — disclosed limitation (Governor ruling 2026-09-18, pre-invocation).** The
raw `pg_dump --schema-only` output of PostgreSQL 16.15 contains generated metadata (`\restrict`
/ `\unrestrict` random token and the `Dumped by` line), so raw hashes differ on every dump — the
launcher's recorded raw values (`309bdf8e6f1ac8a264658f21bfe1c4fd5216bd91469a459e75a3a3b94b5c2a58`
pre, `9c8567883d81f6f2da316433b8160232a95bc913caf3c092af5a51cdb2c5849b` post) are expected noise, and
that line is the only content of `hashes-drift.txt`. The comparison of record is the normalized
dump (those three lines removed), preserved as raw pre/post dumps in the operator bundle:

| dump | raw SHA-256 | normalized SHA-256 |
|---|---|---|
| pre-run (17:39:14Z) | `229e9bc6ef0941bfdf104708d1f5aca7b5684ff7bad181bd705278ac1111472b` | `f7a9c18d79540fed6c5d84051b4e46bc4c6647ff271653c209897ba33726102d` |
| post-run (17:41:30Z) | `5decf47c3005f5573515ef28e2091a93fa3b2f95406a7bb2423e4418378a8975` | `f7a9c18d79540fed6c5d84051b4e46bc4c6647ff271653c209897ba33726102d` |

Normalized pre == post; no real schema drift.

## 5. Clause status (Document A §A7 / ADR-159 D5)

| clause | status |
|---|---|
| A3 pins resolve | PASS |
| A5 pre-run preparation | PASS |
| A6 task statement / invocation | FAIL — runner terminated at bootstrap (exit 64) before receiving the statement |
| I-1 read-only enforcement | NOT EVALUATED (apparatus side held) |
| I-2 output isolation | NOT EVALUATED (apparatus side held) |
| I-3 no later-state leakage / socket-level isolation | NOT EVALUATED by the run; coldroom socket-level containment proven immediately before it |
| I-4 reconstructability | NOT EVALUATED — nothing to reconstruct |
| I-5 mutation boundary | NOT EVALUATED |
| I-6 authority boundary | NOT EVALUATED |
| A10 recall figure | NOT COMPUTED |
| A11 backlog beyond the eight | none |
| A12 honest reporting | this record |

Trial 0 provides no evidence for or against ADR-159 D1. Its recall figure was never a threshold
(D5) and here is not a measurement.

## 6. Retained evidence and custody

Raw evidence is never published (custody procedure step 7); it is retained at the external Trial 0
custody root `/opt/core-trials/adr-159/trial-0/` on the CORE host and, byte-identical, in the
ADR-159 recovery tree on the Proxmox recovery host. Both copies were verified before this record.

| artefact | SHA-256 |
|---|---|
| Custody manifest `manifests/bundle-20260918T173945Z.sha256sums` (24 entries: run bundle 13, operator bundle 8, prior blocked-attempt record 3; `sha256sum -c` 24/24 OK on both copies) | `e3d94d36e167a5fce619e3155305a7a98b8e63bdd1161d56391e38f012d6ac4d` |
| `manifests/bundle-20260918T173945Z.sha256sums.sha256` | `d74441c21716edff0d0393cf4837de32b1c7ad4582b7e9d6ea6e1ce85a35b8e3` |
| `manifests/bundle-20260918T173945Z.verify.txt` (24 OK, exit 0) | `d40e4b7fd3fec636a87d408c50b46803bc4b755d52f713209a1aca3325c256dc` |
| Launcher-internal `evidence/run-20260918T173945Z/MANIFEST.sha256sums` | `56f12b6959a852791d7eeb95de5546a92114b2171672b7292977152dbf0a6b98` |
| `evidence/run-20260918T173945Z/MANIFEST.sha256sums.sha256` | `9923833fbd390bd0e241b348aacd00938e9895337d7fb656af28279f354c2559` |
| Operator bundle `evidence/operator-20260918T173944Z/SHA256SUMS` | `eba98c616505557ca85aa313aea583175719146312f52a510a85eb738ad728b1` |
| Byte-identity list (33 files, computed independently on each custody host, identical) | `7d5fcf888d9329c271be8fd63da57581bb4df7d496ac6c8c34ca8a3b04dcf8b8` |
| Second-copy receipt `second-copy/20260918T173945Z.md` | `ad49207d1965bdf21415c3f286981c079fa69aebbe5105d6fbe39da4bb60e58c` |
| Operator report `operator-report-20260918T173945Z.md` | `51952d626276848820cd40a19c331a1f275dd9e5e6a34f5f8a1f1fb026d93893` |
| Verification record `verification/verification-20260918T173945Z-same-session.md` | `6649fd13edde5074b2efebdf0354bfc926f2f1af94395337ba388a9ede157428` |

**Launcher self-manifest discrepancy (apparatus finding, explained).** Inside the run bundle,
`MANIFEST.sha256sums` lists `evidence/launcher.log` as
`2469c408c3f11ba13be13a756a3124bab8aa2113ad4c02db721321e390e3e473`, while the retained file is
`cd1e34c232d70e3d175de5b698a683d43e86972d49123b442468141e05e8cdf5`: the launcher hashes the log and
then appends its final `frozen …` line. The file minus its last line hashes to the manifest value
exactly. The custody manifest above hashes the retained bytes and verifies.

## 7. Scanner result

Qualified external Gitleaks v8.30.1 (executable
`88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509`, built-in config, no allowlist,
redacted output), run on the complete candidate bundle per custody procedure step 4:
`evidence/` exit 0, `export/` exit 0, operator report exit 0 — **no findings** (`[]` each).
Publication of this record is not blocked.

## 8. Verification record and its limitation

The verification record (`6649fd13edde5074b2efebdf0354bfc926f2f1af94395337ba388a9ede157428`)
re-derived every value above read-only and classified the result VERIFIED with one wording
correction to the operator report (the first `shared` import occurs at external-run step 2b, not
before step 1). **It was produced by the same operator session that ran the trial.** It is
sufficient for recording this pre-bootstrap failure and the custody integrity of the evidence; it
is not represented as the independent verification the custody procedure's step 8 requires for
certifying a successful run.

## 9. Seal-provenance limitation

The Phase-1 seal referenced by this apparatus is the recovered artefact attested in
`adr-159-phase1-seal-digest-20260918.md` (`phase1-benchmark-SEALED.json`
`71835d8b7e905ff8cb1d899b51b6996e2d57f24e01331898de6268c0775d4dd4`, 9421 bytes; `seal_manifest.py`
`a4d5b6d3ac7b9afedc6db9651cc7491851b8583049819f66115ffc4a64a68d7e`, 13061 bytes). Approximately
71 hours separate the sealing event from the backup that preserved it, with no externally recorded
digest in that interval; cryptographic continuity to the moment of sealing is not proven. Both
custody copies were re-verified by digest, size and mtime before and after the trial. This run
produced nothing to score, so the seal was not used.

## 10. Apparatus findings carried forward (not implemented)

1. The launcher must pin an explicit, accessible working directory before invoking the runner.
2. The launcher must finalize its own logging before producing its self-manifest.
3. Raw `pg_dump` schema hashes contain generated metadata; comparisons must use the disclosed
   normalization.
4. Runner handling of an unreadable cwd during discovery is a separate hardening observation
   (§3), not the cause assigned to CORE for this trial.

## 11. What this record does not do

It does not authorize a repetition (no Trial 0-R1), does not change the runner or subject pins,
does not begin Trial 1, does not modify the launcher or any apparatus, and does not rewrite the
result as BLOCKED or PASS. The Governor certifies this record by the commit that lands it, cited in
the ADR-159 Note.
