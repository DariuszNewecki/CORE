# E15 Cold-Room Run — ADR-155 Candidate `3cbe0be0`

**Status:** Evidence record filed. This closes the E15 evidence gap for the ADR-155
"Isolated Consequence-Chain Demo" candidate. It is not itself a final ADR-155 verdict
(Accepted / Accepted-with-limitations / Blocked) — that synthesis, per the governor's
2026-07-26 directive, still requires mapping this evidence together with the Phase 4
matrix, hosted CI, DoD, and reviewer checklist. Claude does not sign attestations; the
governor does.

**Prepared:** 2026-07-26. Evidence collection + a disposable VM lifecycle only — no
change to `src/`, `.intent/`, or this repository's tracked/untracked state.

---

## 1. What E15 requires

Per `.specs/planning/archive/CORE-Isolated-Consequence-Chain-Demo-Spec.md` §6.2:

> **E15 — Cold-room run.** A non-author follows public documentation on a clean
> supported host and completes the demo without source inspection.

## 2. Environment

- **Host:** the user's Proxmox VE 9.2.4 hypervisor (`192.168.20.100`), a machine
  distinct from `/opt/dev` and from any host sharing this session's Postgres/Qdrant.
- **Base image:** VM 300 `core-template` — a pre-existing template built exactly for
  this purpose (references issues **#561**/**#562**; both closed, but for the *prior*
  `scripts/demo.sh`, not this ADR-155 replacement, so their closure does not substitute
  for this run). Per its own description and `scripts/coldroom-prep.sh`: Ubuntu 24.04
  LTS, Python 3.12, Poetry 2.4, Docker + Compose v2, `postgres:16` +
  `qdrant/qdrant:v1.18.0` pre-pulled — **prerequisites only, never CORE itself**.
- **Run instance:** linked-cloned to VM 301 (`core-e15-adr155`), started fresh,
  destroyed immediately after evidence capture.
- **Access deviation (disclosed, and later corrected — see §9):** the template's
  description states "operator SSH key authorized for user `core`." At the time, this
  session incorrectly assumed that key was unavailable and never checked; combined with
  the QEMU guest agent also turning out not to be installed (`coldroom-prep.sh` never
  installs it, so the originally planned no-new-credentials path via `qm guest exec` was
  unusable), the session fell back to a password supplied by the user instead. The
  correction in §9 established that the documented SSH key was, in fact, present the
  whole time in this session's own environment and matched the template's
  `authorized_keys` exactly — the password fallback was an avoidable process gap, not a
  genuine gap in the template. The VM's IP (`192.168.20.49`) was confirmed via a VNC
  screendump (showing a clean `core login:` prompt) cross-checked against Proxmox's ARP
  table by MAC address; that discovery method remains valid regardless of the access
  method used afterward.
- **Operator-identity caveat (disclosed, load-bearing):** the commands below were
  driven by Claude Code — the same agent that implemented and verified ADR-155 in
  prior phases — not a literal independent third-party human. What *was* enforced:
  a host that had never seen `/opt/dev` or this repo before, no shared local
  database/Qdrant, and strict adherence to only the commands documented in
  `README.md` / `docs/getting-started.md` / `docs/cli-reference.md` with no reading of
  `src/` to find or shape the command. Whether that operational discipline satisfies
  "non-author" in spirit, or whether a genuinely separate human operator is still
  required, is a judgment call for the governor.

## 3. Procedure (exactly as publicly documented, no source inspection)

```bash
git clone https://github.com/DariuszNewecki/CORE.git
cd CORE
git checkout 3cbe0be0        # frozen candidate; not yet on main, so pinned explicitly
./install-core.sh
poetry run core-admin demo consequence-chain --output report.md --simulate-confirmation
```

`--simulate-confirmation` is the flag the docs explicitly sanction for CI/cold-room use;
the report correctly labels the confirmation "simulated," not human (D9).

## 4. Install evidence

`install-core.sh` completed cleanly: prerequisites detected (docker, docker compose,
poetry, python 3.12), dependencies installed, `core_postgres_db` / `core_qdrant_db`
containers healthy, schema applied, **offline constitutional audit clean**, API up,
ending in the documented "CORE is yours" banner — matching the spec verbatim, no
warnings papered over.

## 5. Demo evidence — two independent runs, both PASSED

Run 1 was launched backgrounded; its exit code was inferred from the printed `PASSED`
verdict and successful report write, not literally captured — a gap in this session's
process, disclosed rather than glossed over. Run 2 was re-run synchronously specifically
to capture a real `$?`, which doubles as a repeatability check (E05-style: independent
run IDs, findings, proposals, SHAs).

| | Run 1 | Run 2 |
|---|---|---|
| Exit code | not directly captured (inferred PASS) | **`RC=0`** (captured) |
| Run ID | `871ee4fa72a14e80890ef6fc33a95fdf` | `e7de341e01da457f933e602813052e55` |
| Finding | `a4568caf-…` `linkage.assign_ids` @ `demo_onramp_871ee4fa.py` | `b61239d3-…` @ `demo_onramp_e7de341e.py` |
| Proposal | `af7d01e4-…` `fix.ids`, risk=safe | `e3a9cde6-…` `fix.ids`, risk=safe |
| Approval authority | `risk_classification.safe_auto_approval` (approver `autonomous_self_promote`) | same |
| Execution | completed | completed |
| Pre→post SHA | `b68fb223…` → `831fabe8…` | `9c6829c5…` → `d0fa018d…` |
| Resolved finding | `resolved` | `resolved` |
| Re-audit | clean=True, matches=0 | clean=True, matches=0 |
| Operator confirm | simulated | simulated |
| Cleanup | workspace removed | workspace removed |

Run 1's full machine-checked evidence (`report.json`) lists **16/16 fail-closed
assertions passed** (D7 seed-absence + D10.1–D10.15), each with a concrete detail value
(exact SHAs, exact finding/proposal identities) — not bare booleans. Run 2 (`report2.md`)
shows the same structure, independently. Both reports carry the required disclaimer:
"This demonstration proves one isolated consequence chain. It is not a
production-readiness attestation."

One non-blocking observation in both runs' logs: an advisory-level
`chokepoint.advisory.would-deny op_class=create path=report.md … reason=no_capability_context`
line from `body.governance.intent_guard`. It did not block the write (both reports were
written successfully) and was not independently investigated further — flagged here for
visibility, not diagnosed.

## 6. Cleanup verification (independently checked, not just trusted from the CLI's own claim)

After both runs, on the VM:

- `docker ps -a` — only `core_postgres_db` / `core_qdrant_db` (the **base install's own**
  persistent services, unrelated to the demo's disposable infra) remained running.
- `docker network ls` — only `core_default` (base install) plus Docker's default
  `bridge`/`host`/`none` networks. No demo-run-labelled network survived.
- `~/.local/state/core/demo/runs/` — **empty** (both run workspaces fully removed).
- Filesystem search for either run ID anywhere under `/` — **zero matches**.

This satisfies the D11 cleanup contract and the corresponding §6.3 negative-claim bullet
("cleanup leaves a run-labeled container, network, storage object, or child process") —
none did.

## 7. Disposal

VM 301 was stopped and destroyed (`qm destroy 301 --purge 1`) immediately after evidence
capture, per the template's own "clones are disposable — destroy after each verification
run" policy. `qm list` afterward shows only the original `core-template` (300) and the
pre-existing VMs (100, 101) — no residue.

## 8. Verdict: **E15 — PASS with governor-accepted operator-independence deviation**

Not an unqualified independent-user validation. Recorded precisely as:

**E15's mechanical criteria are satisfied**: a clean host that had never seen this
repository, a pinned frozen-candidate checkout, only publicly documented commands, no
source inspection to find or shape the command, a real install, two real passing demo
runs with full fail-closed assertion evidence, and verified-clean disposal.

**Explicitly withheld from unqualified independence:** true operator independence. This
was Claude Code following the documented procedure under discipline, not a separate
human who has never seen the ADR-155 implementation. Per governor decision 2026-07-26:
this deviation does not block acceptance; a genuinely independent human cold-room run
remains a **post-merge validation item**, required before upgrading this from
"PASS with deviation" to an unqualified independent pass.

**Also disclosed, non-blocking:** Run 1's exit code was inferred rather than captured
directly (Run 2's was); the QEMU guest agent is not actually present in the template
despite `agent: 1` in its Proxmox config.

This report does not itself flip ADR-155 to "Accepted" — per the governor's own
sequencing, that requires synthesizing this evidence with the Phase 4 matrix, hosted CI,
DoD, and reviewer checklist into the final acceptance report.

## 9. Post-run credential remediation (governor-directed, 2026-07-26)

A governor review of the draft of this report caught that §2 originally stated the
`core` account's password in plaintext. That value has been removed from this report
(it was never committed or pushed — caught before the first commit). Remediation taken:

- **The "SSH key unavailable" claim in the original §2 was itself wrong, and is
  corrected here rather than left standing.** Re-checking after the governor's review
  found the documented operator SSH key (`~/.ssh/id_ed25519`, `d.newecki@gmail.com`)
  present in this session's own environment the entire time, and it matches `core`'s
  `authorized_keys` on the template exactly byte-for-byte. The password fallback used
  during the original run was an avoidable process gap — the session didn't check for
  an available key before reaching for a workaround — not a real absence of the
  documented access path.
- The disclosed password was rotated on the `core-template` (VM 300): un-templated it
  (`qm set 300 --template 0`), started it, connected via the now-confirmed-working SSH
  key, and ran `chpasswd` — verified via the shadow hash (`crypt.crypt` check) and via a
  password-only connection attempt (`look_for_keys=False`) that the old value no longer
  authenticates and the new one does.
- **Password SSH authentication was then disabled entirely** on the template
  (`PasswordAuthentication no` / `KbdInteractiveAuthentication no`, via
  `/etc/ssh/sshd_config.d/10-disable-password-auth.conf` — named `10-` specifically to
  sort and win over a pre-existing `50-cloud-init.conf` drop-in that explicitly set
  `PasswordAuthentication yes` and silently overrode the first attempt at this fix).
  Verified via `sshd -T` (effective config) and a live connection test: key auth works,
  password auth (old and new value both) is now rejected outright. This makes the
  template's own documented claim — "operator SSH key authorized… passwordless sudo" —
  actually true and exclusively true, closing the access-method gap rather than papering
  over it with a rotated-but-still-guessable password.
- VM 300 was shut down cleanly from inside (`sudo shutdown -h now`) and re-flagged as a
  template (`qm set 300 --template 1`) — restored to its normal state, ready for future
  linked clones with key-only access baked in.
- Future template clones inherit key-only access, not a reusable disclosed password.
- The `qemu-guest-agent` gap (§2, §8) is unrelated to this fix and remains open — worth
  installing so `qm guest exec` works as the template's own tooling intended, but not
  required now that key-based SSH is confirmed reliable. Tracked as template/infra
  follow-up, not a repo issue (it's local infrastructure, not CORE source).
