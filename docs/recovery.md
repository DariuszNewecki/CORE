# Recover a CORE install

This page describes how to bring back a CORE production install. The backup is the Proxmox
nightly backup of the whole CORE VM, and the first way back is to restore that image. The second
way, rebuilding from parts, is for when no image is usable. The recovery drill (#1070) restores the
image on a throwaway VM, checks it, then destroys the VM. The page lists paths only. No secret value
appears here.

Every step names who runs it:

- **host admin (darek, outside CORE)**: the person with root on the hypervisor and the VM. Every
  setup script and `core-deploy` needs root. The governor's CORE account holds no sudo, so these
  steps happen outside CORE.
- **a CORE account**: `core` (the services), `core-law` (the law's custodian), `core-runner` (the
  deploy pipeline). These accounts act on their own, through the units and scripts, once the host
  admin has set them up.

## The backup: Proxmox nightly VM backup

- **What:** the Proxmox backup job for VM 200, the CORE VM. It runs every night at 02:30 and makes a
  `vzdump-qemu-200-<date>.vma.zst` archive (15.4 GB on 2026-10-16).
- **Where:** on the Proxmox host `pve`, in storage `backup` (`/ZFS-pool/backup`). That is a
  different disk from the VM's own (`local-lvm`).
- **Contains:** the VM's whole disk, so every part in the table below, the unique ones included.
- **Can lose:** up to 24 hours, that is everything since the last 02:30 run.
- **Live snapshot:** the backup is taken while the VM runs. After a restore, PostgreSQL replays its
  log on first start (about 2.5 minutes in the drill).
- **Limit:** the archive sits on the same physical Proxmox host as the VM. Losing `pve` loses both.
  How long archives are kept is set in the backup job on `pve`.

## Restore from the VM backup

Every step is the **host admin (darek, outside CORE)**'s: `qm` runs on `pve`, and commands inside
the VM run as root through `qm guest exec <vmid> --`. The guest agent works on a restored VM.

| # | Step | Note |
|---|---|---|
| 1 | `qmrestore <archive> <vmid> --storage ZFS-pool --unique 1` | a drill uses a new `<vmid>`; a real restore replaces VM 200 |
| 2 | Before the first boot: `qm set <vmid> --delete ide2,cicustom,ipconfig0,nameserver,searchdomain` (remove the cloud-init drive). A drill clone also gets `qm set <vmid> --name core-restore-drill --net0 <…>,link_down=1 --onboot 0` | without step 2, cloud-init would run its setup again: reset passwords, upgrade packages, re-own `/mnt/vector_db`. The drill clone must not reach the network next to the live VM. The new name is not needed for isolation (the guest keeps its hostname `core`, and its network is down); it keeps `qm list` and the Proxmox UI from showing two VMs named `core`. `qmrestore` has no `--name`, so step 2 sets it |
| 3 | `qm start <vmid>`, then wait until `qm agent <vmid> ping` answers | |
| 4 | Drill clone only, as soon as the agent answers: `systemctl stop core-pipeline.timer core-law-auto-apply.timer core-law-digest.timer` (the two law timers exist only in backups from before 2026-10-18; stopping a missing timer is harmless) | see [Timers on a restored VM](#timers-on-a-restored-vm) |
| 5 | Wait for PostgreSQL to finish crash recovery | about 2.5 minutes after boot; see [Startup on a restored VM](#startup-on-a-restored-vm) |
| 6 | Wait until `curl http://127.0.0.1:8000/health` answers `{"status":"ok"}`. Do not restart anything | the API retries by itself while PostgreSQL recovers, at most a minute apart ([#1092](https://github.com/DariuszNewecki/CORE/pull/1092)); it reaches Qdrant on loopback, with or without network ([#1088](https://github.com/DariuszNewecki/CORE/issues/1088)) |
| 7 | The checks in [Check the result](#check-the-result) | the audit and the law check run as `core-claude` ([#1089](https://github.com/DariuszNewecki/CORE/issues/1089)) |
| 8 | Drill only: `qm stop <vmid> && qm destroy <vmid> --purge 1 --destroy-unreferenced-disks 1` | leaves no disks, config or job entries |

### Timers on a restored VM

The backup restores `core-pipeline` enabled (deploys approved promotions, first run 2 minutes
after boot). A backup from before 2026-10-18 also restores `core-law-auto-apply` (applied record-only law
without a merge, first run 5 minutes after boot) and `core-law-digest` (a daily read-only digest);
core-law-setup now removes both. They are not stopped before the first boot,
because that would mean editing the VM's disk from `pve` ([#1090](https://github.com/DariuszNewecki/CORE/issues/1090)).

- **Drill clone:** step 2 takes its network down before the first boot. The pipeline cannot reach
  GitHub, so it can neither fetch nor deploy, and law auto-apply writes only the clone's own disk,
  which step 8 destroys. Step 4 stops all three as soon as the guest agent answers (about 40 s
  after boot), before the first one is due. They are not started again: the clone is destroyed.
- **Real restore (replaces VM 200):** leave `core-pipeline` enabled. The restored VM is CORE again,
  and the pipeline then deploys a promotion approved after the backup. If the two law timers came back,
  remove them at once: `sudo core-law-setup --governor core-darek --apply`. The Services check
  confirms what is active.

### Startup on a restored VM

While PostgreSQL replays its log, the services that need it restart on their own. In the
2026-10-17 drill:

- `core-api` restarted twice through its retry ([#1092](https://github.com/DariuszNewecki/CORE/pull/1092)), then answered `{"status":"ok"}`.
- `core-daemon` and 15 `core-daemon-worker@` units restarted once each, on their 2-minute watchdog.

This is expected. Everything came back without a manual step, so these restarts are not a gap.
Restart nothing by hand (step 6).

## Rerun: 2026-10-17

The rerun restores the nightly backup of 2026-10-17 02:30, `vzdump-qemu-200-2026_10_17-02_30_*.vma.zst`,
with the restore steps above and nothing else. It is a clean pass when:

- step 6 needs no restart and no address alias: the proof for [#1092](https://github.com/DariuszNewecki/CORE/pull/1092) and [#1088](https://github.com/DariuszNewecki/CORE/issues/1088);
- every row in [Check the result](#check-the-result) is healthy, the audit included: PASS, with the
  user and command named there;
- the data check finds `core.blackboard_entries` rows up to the backup's start;
- no step needs a fix that is not written on this page.

What changed in the live VM before that backup, on 2026-10-16:

- The dev checkout follows each deploy ([#1063](https://github.com/DariuszNewecki/CORE/issues/1063)). The 3f3ab7fa deploy moved it from 354d17fd;
  its offline audit is PASS and `law check-tree` exits 0.
- Nine stale `.specs/` files and a duplicate custody line were removed from `/opt/dev/CORE` and
  `/opt/core/law` (host admin, once). They came from proposals that predate main's deletions.
- All 36 law proposals are superseded by main and moved to `/opt/dev/CORE/var/law-proposals-withdrawn/`,
  so neither `law apply` nor the timer can apply one again ([#1096](https://github.com/DariuszNewecki/CORE/issues/1096) adds the guard).
- `QDRANT_URL` is moved to loopback by core-runtime-setup ([#1088](https://github.com/DariuszNewecki/CORE/issues/1088)).

"Same state as before" for this rerun, without anything recorded by hand:

- `runuser -l core-claude -c 'git -C /opt/dev/CORE rev-parse HEAD'` on the clone equals `readlink /opt/core/current` on the clone
  (the checkout follows the live release);
- the clone's `/opt/core/custody/ledger.jsonl` is a prefix of the live VM's (lines added after 02:30
  are the only difference);
- the open-findings count (the open-findings row in [Check the result](#check-the-result)) is compared with the live VM's; a
  difference must be explained by work after 02:30.

## Drill record: 2026-10-16

- **Restored from:** `vzdump-qemu-200-2026_10_16-02_30_01.vma.zst` (15.4 GB, nightly job, TASK OK),
  storage `backup` on `pve`.
- **Restored to:** VM 990 `core-restore-drill` on `ZFS-pool`, a different disk from the live VM 200.
  It was isolated from the network the whole time, then destroyed. VM 200 kept running throughout.

| # | Step | Time | Result |
|---|---|---|---|
| 1 | Restore the archive | 7 min 48 s | ok |
| 2 | Isolate before first boot (net link down, no onboot, 12 GB / 8 cores, cloud-init drive removed) | 3 s | ok |
| 3 | Boot until the guest agent answers | 38 s | ok |
| 4 | Stop the timers that write | under 5 s | ok |
| 5 | PostgreSQL crash recovery | about 2.5 min | ok, automatic |
| 6 | Start the API | 46 s | ok only after a manual restart ([#1087](https://github.com/DariuszNewecki/CORE/issues/1087)) and a loopback alias for Qdrant ([#1088](https://github.com/DariuszNewecki/CORE/issues/1088)) |
| 7 | `core-admin law check-tree --json` | 18 s | exit 0: no refusals, law loads, 140 intent files valid, 0 dangling |
| 8 | `core-admin code audit --offline --severity block` | 68 s | **DEGRADED**: three `.intent/` files differ from the last commit, as on the live checkout ([#1063](https://github.com/DariuszNewecki/CORE/issues/1063)) |
| 9 | Data check: `core.blackboard_entries` | 4 s | 2,303 rows from the day of the backup, the last one 2 s before the backup started; 17,521 rows from the day before |
| 10 | Destroy the clone | 5 s | nothing left |

- **Total:** about 16 minutes of work, 12:33:42 to 12:57:59 including diagnosis. False starts are
  not in the table (the audit first run as `core-law`, then as `core-claude`; `law check-tree`
  without a path). The full log is `/root/drill-990.log` on `pve`.
- **Time to recover once the findings are fixed:** about 13 minutes: restore 8 min, boot and
  database recovery about 3 min, checks about 2 min.
- **Result: not a clean pass.** The data is complete, but the API did not come back by itself and
  the audit is DEGRADED. #1070 stays open until a rerun passes clean.

**Findings**

1. A restored clone would run cloud-init's setup again. Removing the cloud-init drive before the
   first boot is now step 2 of the restore.
2. The API did not come back by itself when PostgreSQL started slowly, as after a restore or a
   power loss: it started before PostgreSQL was ready, exited 0, and `Restart=on-failure` did not
   restart it ([#1087](https://github.com/DariuszNewecki/CORE/issues/1087)). A clean reboot is not
   affected: on 2026-10-16 at 13:44 the live VM rebooted, and the API answered after 64 s with 0
   restarts. [#1092](https://github.com/DariuszNewecki/CORE/pull/1092) fixes it; the #1070 rerun
   is the proof.
3. `QDRANT_URL` pointed at the VM's LAN address, not loopback ([#1088](https://github.com/DariuszNewecki/CORE/issues/1088)). Fixed: core-runtime-setup
   moves it to loopback.
4. The audit was DEGRADED because three `.intent/` files that core-law changed on 2026-10-15 were
   uncommitted ([#1063](https://github.com/DariuszNewecki/CORE/issues/1063)). The restore did not cause this; the live checkout showed the same.
   Fixed: each deploy moves the checkout to the deployed commit.
5. No single user and command ran the offline audit on a restored host ([#1089](https://github.com/DariuszNewecki/CORE/issues/1089)). Fixed: `core-claude`
   with the checkout's `.venv`, see [Check the result](#check-the-result).
6. A restored VM starts with every timer enabled. On the isolated clone, the pipeline ran once and
   failed on DNS ([#1090](https://github.com/DariuszNewecki/CORE/issues/1090)). Settled: see [Timers on a restored VM](#timers-on-a-restored-vm).
7. The clone was capped at 12 GB and 8 cores because the host had about 28 GB free, so it did not
   match production (24 GB, 12 cores).

## Drill record: 2026-10-17

- **Restored from:** `vzdump-qemu-200-2026_10_17-02_30_03.vma.zst`, storage `backup` on `pve`.
- **Restored to:** VM 990 on `ZFS-pool`. It kept the name `core` (see step 2). It was isolated from
  the network the whole time, then destroyed. VM 200 was not touched.

| # | Step | Time | Result |
|---|---|---|---|
| 1 | Restore the archive | 10 min 46 s | ok |
| 2 | Isolate before first boot | 2 s | ok |
| 3 | Boot until the guest agent answers | 33 s | ok |
| 4 | Stop the timers that write | 3 s | ok |
| 5 | PostgreSQL crash recovery | ready 2 min 19 s after start | ok, automatic |
| 6 | Start the API | `{"status":"ok"}` 4 min 29 s after start | ok, with no manual restart and no alias ([#1092](https://github.com/DariuszNewecki/CORE/pull/1092), [#1088](https://github.com/DariuszNewecki/CORE/issues/1088)) |
| 7 | The checks | 2 min 56 s | see below |
| 8 | Destroy the clone | 5 s | nothing left |

- **Total:** 21 min 22 s; from the restore's start to the API, 15 min 48 s.
- **Checks:**
  - Audit: PASS, 0 blocking.
  - Law: `law check-tree` exit 0.
  - Workers: 37 of 38 alive; the Goal Execution Worker is not counted, as the Workers row says.
  - Sandbox: 8 of 8 passed.
  - Ledger: identical to VM 200's.
  - Checkout: equals the live release b06e1444.
  - Data: the last row at 02:29:51, 11 s before the backup.
  - Not run: Database, Pipeline, open-findings.
- **Logs:** `/root/drill-990-2026-10-17.log` and `/root/drill-990-2026-10-17-checks.txt` on `pve`.
- **Result: not a clean pass**, because of the page gaps below. #1070 stays open.

**Findings**

1. `core-admin` is not on root's `PATH`, so the Database, Pipeline and open-findings checks did not
   run. Fixed: every row in [Check the result](#check-the-result) names its user and full path.
2. The Services row expected the three timers active, but step 4 stops them on a drill clone.
   Fixed: the row states the drill exception.
3. The Data query also counted rows the clone wrote after boot. Fixed: it stops at PostgreSQL's
   start on the clone.
4. At startup the API restarted twice and `core-daemon` and 15 workers once each, all by
   themselves. Settled as expected: see [Startup on a restored VM](#startup-on-a-restored-vm).
5. The page did not say whether a drill clone must be renamed; it kept the name `core`. Settled: it
   need not be for isolation; step 2 renames it so the two VMs are told apart.

## What a complete backup contains

Rebuildable means that git (by commit SHA), GitHub or PyPI can make the part again. Unique means
that only a backup can bring it back. Every part lives on the VM's disk, so the nightly VM backup
holds all of them; the last column says what else exists.

| Part | Where it lives | Kind | Backup |
|---|---|---|---|
| Database | PostgreSQL container `core_postgres_db`, volume `core_postgres_data` (`docker-compose.yml`) | unique | nightly VM backup; also a dump `/opt/core/backups/<stamp>-pre-<sha12>.dump` before each deploy that migrates, restore-checked by core-deploy (see [The pre-migration dump](#the-pre-migration-dump)) |
| Vector store | Qdrant (`QDRANT_URL` in `/opt/core/etc/core.env`; storage `/mnt/vector_db/core_qdrant_db` in compose, the VM's second disk `scsi1` = `/dev/sdb`) | derived (re-embedding takes hours) | nightly VM backup: the Proxmox job includes `scsi1` as well as `scsi0` (verified in the 2026-10-23 job log); see [Vector store](#vector-store) |
| Law, as committed | `/opt/dev/CORE/.intent`, `/opt/dev/CORE/.specs` | rebuildable | git (GitHub) |
| Release law | `/opt/core/law/.intent`, `/opt/core/law/.specs` | rebuildable | from git; core-law writes it on each apply |
| Custody ledger | `/opt/core/custody/ledger.jsonl` (only lines from before the move are in git, in `.intent/custody/ledger.jsonl`) | unique | nightly VM backup |
| Ledger signing key | `/opt/core-law/home/.ssh/core_law_ledger` (the public half is in git as `.intent/custody/allowed_signers`) | unique | nightly VM backup |
| Deploy ledger | `/opt/core/deploy-ledger.jsonl` (`core-deploy --rollback` reads it) | unique | nightly VM backup |
| Runtime secrets | `/opt/core/etc/secrets.env` (`DATABASE_URL`, `CORE_MASTER_KEY`); its sources `/opt/dev/CORE/.env` and `/opt/dev/CORE/.secrets/core.env` | unique | nightly VM backup. Without `CORE_MASTER_KEY`, the secrets stored in the database cannot be read |
| Host config | `/opt/core/etc/deploy.conf`, `/opt/core/etc/core.env` | hand-edited | nightly VM backup; the examples are in `infra/systemd/d2/` |
| Pipeline config | `/etc/core/pipeline.conf` | rebuildable | core-one-path-setup writes it |
| Pipeline token | `/etc/core/pipeline-github-token` (optional) | re-issuable | nightly VM backup; it can also be issued again on GitHub |
| Private-names config | `/opt/core/law/private-names/` (`private-names.conf`, `names.txt`) | unique | nightly VM backup. Without it, the assistant's commits and gh writes are refused |
| On-disk history | `/opt/dev/CORE/var/law-proposals/`, `/opt/dev/CORE/var/law-proposals-withdrawn/`, `/var/lib/core-pipeline/logs/`, `/opt/dev/CORE/.intent/keys/` | unique | nightly VM backup |
| Releases | `/opt/core/releases/<sha>/`, `/opt/core/current` | rebuildable | core-deploy builds them by SHA |
| Custodian venv | `/opt/core-law/venv` | rebuildable | core-law-setup installs it from the live release (its second run on a fresh host) |
| Service units | core's user units in `~core/.config/systemd/user/` (sources in `infra/systemd/d2/`); system units in `/etc/systemd/system/`: the sandbox units (`infra/systemd/sandbox/`), the pipeline and law timers (generated by `infra/core-one-path-setup` and `infra/core-law-setup`) | rebuildable | the setup scripts write them |
| Accounts | `core`, `core-claude`, `core-darek`, group `core-dev` (no script creates them); `core-law`, `core-runner`, `core-build`, `core-sandbox`, group `core-gov` (the setup scripts create them) | rebuildable | listed here |

## The pre-migration dump

Before a deploy migrates the schema, `core-deploy --migrate` stops every unit and dumps the
database (`BACKUP_COMMAND` in `/opt/core/etc/deploy.conf`) to
`/opt/core/backups/<stamp>-pre-<sha12>.dump`. It then checks the dump before anything migrates
([#1113](https://github.com/DariuszNewecki/CORE/issues/1113)). core-deploy runs every step, as
root; nothing is done by hand.

| # | Step | On failure |
|---|---|---|
| 1 | `pg_restore --list <dump>` must read the dump | refused: units restarted, nothing migrated |
| 2 | Row counts on the live database, read-only (`PSQL_COMMAND`, in a `BEGIN TRANSACTION READ ONLY`). Every unit is still stopped, so these are the counts at dump time | refused |
| 3 | The dump is restored into a throwaway cluster: a container of the server's own image (`RESTORE_IMAGE`), `--network none`, removed afterwards (`docker rm -f` even after a timeout of one hour). A new cluster in a temp dir inside it, `pg_restore --no-owner --no-privileges --exit-on-error`, then the same row counts. The live server is never written | refused |
| 4 | Every table's count in the copy must equal the live count | refused; the tables that differ are recorded |

The result is written next to the dump as `<dump>.check.json` (verdict, reason, the live counts,
the tables that differ, the end of the error output), and on a deploy that goes live also in its
deploy-ledger line as `backup_check`. `pg_restore --list` reads only the dump's table of contents:
a dump cut off halfway still lists, and only the restore in step 3 finds it.

Why refuse, not warn: until the migration runs, refusing costs only time (the old release keeps
running on its own schema). After it, the dump is the only way back. A dump that does not
restore is no backup.

Without `PSQL_COMMAND` or `RESTORE_IMAGE` the dump is only listed (step 1), and the deploy warns
and records the verdict `unchecked`. `core-one-path-setup` adds both when missing, from
`DATABASE_URL` and the `core_postgres_db` container.

**Restore the newest dump by hand** (host admin, as root; the steps the check runs, ending in
a table list with sizes):

```
dump=$(ls -t /opt/core/backups/*-pre-*.dump | head -1)
image=$(grep '^RESTORE_IMAGE=' /opt/core/etc/deploy.conf | cut -d= -f2-)
pg_restore --list "$dump" | head
docker run --rm -i --network none --user postgres --entrypoint /bin/sh "$image" -c '
  d=$(mktemp -d); initdb -D $d/data -U postgres -A trust >/dev/null
  pg_ctl -D $d/data -l $d/log -s -w -o "-c listen_addresses= -c unix_socket_directories=$d" start
  createdb -h $d -U postgres restore_check
  pg_restore -h $d -U postgres -d restore_check --no-owner --no-privileges --exit-on-error
  psql -h $d -U postgres -d restore_check -c "\dt+ core.*"' < "$dump"
```

To restore a dump into the live database itself, see step 5 of [Rebuild from parts](#rebuild-from-parts).

**Record:** no deploy has migrated since the check exists. The next deploy that migrates
records the first result in its ledger line and `<dump>.check.json`.

## Vector store

The Proxmox nightly VM backup (02:30, 7 daily, 4 weekly, 3 monthly) includes both of VM 200's
disks: `scsi0` (system) and `scsi1` (40G, `/dev/sdb`, where Qdrant keeps its data). Neither has
`backup=0`, and the 2026-10-23 job log lists `include disk 'scsi0'` and `include disk 'scsi1'`.
A separate snapshot job (#1241) was removed again for that reason (#1081). The restore drill
(#1070) proves it: in the restored VM, every collection's point count must match the table.

**What is in it.** Eight collections, all derived from files in the repository. Rebuilding them
means embedding every file again (`nomic-embed-text`, thousands of calls, hours), so the VM backup
is the way back and the rebuild is the fallback.

| Collection | Points (2026-10-23) | Source | Rebuild command (fallback) |
|---|---|---|---|
| `core-code` | 6,898 | `src/**` | `core-admin vectors rebuild --write --yes` |
| `core-tests` | 7,469 | `tests/**` | same |
| `core-docs` | 615 | `docs/**`, infra SQL | same |
| `core-prompts` | 156 | `var/prompts/**` | same |
| `core-patterns` | 2,492 | `.intent/**` | same (both of its phases write it) |
| `core_policies` | 265 | `.intent/rules/**` | same (phase 2) |
| `core_specs` | 2,546 | `.specs/**` | same (phase 2) |
| `governance_claims` | 516 | `.intent/` and `.specs/` claims | `core-admin coherence seed bootstrap` |

None of these rebuild commands has been run end to end against an empty Qdrant.

## Backup by parts

This is for when no VM image can be used, for example moving CORE to other hardware. It is not
scheduled.

**host admin (darek, outside CORE)**, on the live host, as root:

1. Dump the database and its globals:
   `docker exec core_postgres_db pg_dump -U <db-user> -Fc <db-name>` and
   `docker exec core_postgres_db pg_dumpall -U <db-user> --globals-only`.
   The user and database name are in `DATABASE_URL` in `/opt/core/etc/secrets.env`.
2. Copy these unique files, keeping owner and mode (`tar --numeric-owner -cpf`):
   - `/opt/core/etc/` (secrets.env, deploy.conf, core.env);
   - `/opt/dev/CORE/.env`, `/opt/dev/CORE/.secrets/`;
   - `/opt/core/custody/`, `/opt/core/deploy-ledger.jsonl`;
   - `/opt/core-law/home/.ssh/`;
   - `/opt/core/law/private-names/`;
   - `/etc/core/pipeline-github-token` (if present);
   - `/opt/dev/CORE/var/law-proposals/`, `/opt/dev/CORE/var/law-proposals-withdrawn/`,
     `/var/lib/core-pipeline/`;
3. Record the live commit (`readlink /opt/core/current`) and, for the check at the end, the
   pre-drill state:
   - `sha256sum /opt/core/custody/ledger.jsonl`;
   - `runuser -l core-claude -c 'git -C /opt/dev/CORE rev-parse HEAD'`;
   - the open-findings count (the open-findings row in [Check the result](#check-the-result)).
4. Encrypt the archive and keep it off the host. The archive holds every secret CORE has.

## Rebuild from parts

Use this only without a usable VM image. The VM is a Proxmox linked clone of `core-template`. That template is an Ubuntu VM prepared with
`scripts/coldroom-prep.sh`: Docker, Poetry, the Postgres and Qdrant images and the guest agent, but
no CORE. The drill destroys the clone at the end.

Write each step's start and end time in the drill record. The total is the time to recover.

| # | Step | Who |
|---|---|---|
| 1 | On the Proxmox host: `qm clone <core-template-vmid> <drill-vmid> --name core-drill` (a linked clone), then `qm start <drill-vmid>`. Find its address with `qm guest exec <drill-vmid> -- ip -br addr` | host admin (darek, outside CORE) |
| 2 | Copy the encrypted backup to the VM and decrypt it there | host admin (darek, outside CORE) |
| 3 | Create the accounts no script creates: `core`, `core-claude`, `core-darek` and group `core-dev`. The governor `core-darek` must not be in `sudo`, `docker` or another root-equivalent group | host admin (darek, outside CORE) |
| 4 | Clone CORE into `/opt/dev/CORE` and check out the recorded commit. Restore `/opt/dev/CORE/.env` and `/opt/dev/CORE/.secrets/` from the backup | host admin (darek, outside CORE) |
| 5 | Start PostgreSQL (`docker compose up -d postgres` in `/opt/dev/CORE`). Restore the globals with `psql`, then the dump with `pg_restore --clean --if-exists -d <db-name>`, both through `docker exec -i core_postgres_db` | host admin (darek, outside CORE) |
| 6 | Start Qdrant (`docker compose up -d qdrant`), or point `QDRANT_URL` at the existing store. Its data comes back with the VM's disk `scsi1`; without it, rebuild the collections, see [Vector store](#vector-store) | host admin (darek, outside CORE) |
| 7 | Restore `/opt/core-law/home/.ssh/`, `/opt/core/law/private-names/` and `/opt/core/custody/` from the backup. Then `sudo /opt/dev/CORE/infra/core-law-setup --governor core-darek`, first without `--apply` (plan only), then with `--apply`: it creates `core-law`, seeds the release law `/opt/core/law/.intent` and `.specs` from the dev tree, and keeps the restored key and private-names config. Nothing is deployed yet, so it skips the custodian venv and its timers ([#1085](https://github.com/DariuszNewecki/CORE/issues/1085)) | host admin (darek, outside CORE) runs it; core-law then owns the law |
| 8 | `sudo /opt/dev/CORE/infra/core-runtime-setup --ref <sha> --governor core-darek`, first without `--apply` (plan only), then with `--apply`. Then restore `/opt/core/etc/secrets.env`, `deploy.conf` and `core.env` from the backup over the files it made | host admin (darek, outside CORE) |
| 9 | `sudo core-deploy <sha> --promotion <PR>` (core-runtime-setup installed it; `<PR>` is the promotion that made `<sha>` live): builds the release, switches `/opt/core/current`, starts the services | host admin (darek, outside CORE) runs it; the units then run as `core` |
| 10 | `sudo /opt/dev/CORE/infra/core-law-setup --governor core-darek --apply` again: it installs the custodian venv from the live release and the law timers | host admin (darek, outside CORE) |
| 11 | `sudo bash /opt/dev/CORE/infra/core-one-path-setup --ref <sha>`: the pipeline account, `/etc/core/pipeline.conf`, the timer, `BACKUP_COMMAND` if missing. Restore `/etc/core/pipeline-github-token` if one is used | host admin (darek, outside CORE) runs it; the timer runs as `core-runner` |
| 12 | Restore `/opt/core/deploy-ledger.jsonl`, `/opt/dev/CORE/var/law-proposals/`, `/opt/dev/CORE/var/law-proposals-withdrawn/` and `/var/lib/core-pipeline/` from the backup | host admin (darek, outside CORE) |
| 13 | Check the result (next section) | host admin (darek, outside CORE) runs the root checks; `core` runs the rest |
| 14 | Destroy the VM: `qm stop <drill-vmid>`, then `qm destroy <drill-vmid> --purge`. Delete the decrypted backup copy | host admin (darek, outside CORE) |

A step that needs a fix not written here is a gap. Record the gap as an issue, update this page in
the same PR, and run the drill again. #1070 allows no undocumented fixes.

## Check the result

The audit and the law check run as `core-claude`, with the dev checkout's own environment
`/opt/dev/CORE/.venv` ([#1089](https://github.com/DariuszNewecki/CORE/issues/1089)). Run them as
root with `runuser -l`, so that `core-claude`'s home and git settings apply. Other accounts fail:

- `core-law`: git refuses the repository, which root owns ("dubious ownership").
- The release's `core-admin` (`/opt/core/current/venv`): it audits its own installed CLI, not the
  checkout's, and lacks `core-cli`, so the CLI checks block.

`core-claude` can read neither `/opt/dev/CORE/.env` nor the secrets; the offline audit needs
neither. The checkout must be at the deployed commit, which every deploy now sees to
([#1063](https://github.com/DariuszNewecki/CORE/issues/1063)).

| Check | Command | Healthy |
|---|---|---|
| Audit | `runuser -l core-claude -c 'cd /opt/dev/CORE && .venv/bin/core-admin code audit --offline'` | PASS, or DEGRADED with 0 blocking findings |
| Law | `runuser -l core-claude -c 'cd /opt/dev/CORE && .venv/bin/core-admin law check-tree'` | exit 0 |
| Database | `sudo runuser -u core -- bash -c 'set -a; . /opt/core/etc/core.env; /opt/core/current/venv/bin/core-admin database status'` (`core` reads the database credential through `CORE_SECRETS_FILE` in `core.env`) | exit 0 (current) |
| Data | `docker exec core_postgres_db psql -U <db-user> -d <db-name> -Atc "select max(created_at) from core.blackboard_entries where created_at < pg_postmaster_start_time()"` (user and database from `DATABASE_URL` in `/opt/core/etc/secrets.env`). Rows from after PostgreSQL started on the clone are the clone's own and are left out | a time within minutes before the backup started |
| API | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| Workers | `curl http://127.0.0.1:8000/v1/daemon/status` | every worker whose last heartbeat before the backup was within its last hour is alive again, with a heartbeat after the boot. Rows last seen long before the backup (on 2026-10-16: 19 test registrations from June and the Goal Execution Worker, last seen 2026-09-13) are not counted |
| Services | `systemctl --user -M core@ status core-daemon core-api 'core-daemon-worker@*'` and `systemctl status core-sandbox.socket core-pipeline.timer` | both active, and no `core-law-auto-apply` or `core-law-digest` unit. On a drill clone the pipeline timer is inactive: step 4 stops it |
| Sandbox | `sudo runuser -u core -- bash -c 'set -a; . /opt/core/etc/core.env; /opt/core/current/venv/bin/core-admin runtime sandbox-check --mode service'` | every row `passed` |
| Pipeline | `runuser -l core-claude -c '/opt/core/current/venv/bin/core-admin runtime status'` | `live commit` is the recorded commit. On a drill clone `main` cannot be read from GitHub (no network) |
| Open findings | `curl -s http://127.0.0.1:8000/v1/status/health \| python3 -I -c 'import json,sys; print(sum(r["count"] for r in json.load(sys.stdin)["blackboard"] if r["entry_type"]=="finding" and r["status"]=="open"))'` | equal to the value recorded at backup time, or the difference explained |
| Same state as before | `sha256sum /opt/core/custody/ledger.jsonl`, `runuser -l core-claude -c 'git -C /opt/dev/CORE rev-parse HEAD'`, the open-findings count (row above) | equal to the values recorded at backup time |
