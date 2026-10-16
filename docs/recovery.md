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
| 2 | Before the first boot: `qm set <vmid> --delete ide2,cicustom,ipconfig0,nameserver,searchdomain` (remove the cloud-init drive). A drill clone also gets `qm set <vmid> --net0 <…>,link_down=1 --onboot 0` | without step 2, cloud-init would run its setup again: reset passwords, upgrade packages, re-own `/mnt/vector_db`. The drill clone must not reach the network next to the live VM |
| 3 | `qm start <vmid>`, then wait until `qm agent <vmid> ping` answers | |
| 4 | Drill clone only, as soon as the agent answers: `systemctl stop core-pipeline.timer core-law-auto-apply.timer core-law-digest.timer` | see [Timers on a restored VM](#timers-on-a-restored-vm) |
| 5 | Wait for PostgreSQL to finish crash recovery | about 2.5 minutes after boot |
| 6 | `systemctl --user -M core@ restart core-api`, then check `curl http://127.0.0.1:8000/health` | needed until the API comes back by itself ([#1087](https://github.com/DariuszNewecki/CORE/issues/1087)). Without network, Qdrant is not reached until [#1088](https://github.com/DariuszNewecki/CORE/issues/1088) is fixed |
| 7 | The checks in [Check the result](#check-the-result) | the audit and the law check run as `core-claude` ([#1089](https://github.com/DariuszNewecki/CORE/issues/1089)) |
| 8 | Drill only: `qm stop <vmid> && qm destroy <vmid> --purge 1 --destroy-unreferenced-disks 1` | leaves no disks, config or job entries |

### Timers on a restored VM

The backup restores three timers enabled: `core-pipeline` (deploys merged commits, first run 2
minutes after boot), `core-law-auto-apply` (applies record-only law, first run 5 minutes after
boot) and `core-law-digest` (a daily read-only digest). They are not stopped before the first boot,
because that would mean editing the VM's disk from `pve` ([#1090](https://github.com/DariuszNewecki/CORE/issues/1090)).

- **Drill clone:** step 2 takes its network down before the first boot. The pipeline cannot reach
  GitHub, so it can neither fetch nor deploy, and law auto-apply writes only the clone's own disk,
  which step 8 destroys. Step 4 stops all three as soon as the guest agent answers (about 40 s
  after boot), before the first one is due. They are not started again: the clone is destroyed.
- **Real restore (replaces VM 200):** leave them enabled. The restored VM is CORE again, and the
  pipeline then deploys what was merged after the backup. The Services check confirms they are
  active.

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
3. `QDRANT_URL` points at the VM's LAN address, not loopback ([#1088](https://github.com/DariuszNewecki/CORE/issues/1088)).
4. The audit is DEGRADED because three `.intent/` files that core-law changed on 2026-10-15 are
   uncommitted ([#1063](https://github.com/DariuszNewecki/CORE/issues/1063)). The restore did not cause this; the live checkout shows the same.
5. No single user and command run the offline audit on a restored host ([#1089](https://github.com/DariuszNewecki/CORE/issues/1089)).
6. A restored VM starts with every timer enabled. On the isolated clone, the pipeline ran once and
   failed on DNS ([#1090](https://github.com/DariuszNewecki/CORE/issues/1090)).
7. The clone was capped at 12 GB and 8 cores because the host had about 28 GB free, so it did not
   match production (24 GB, 12 cores).

## What a complete backup contains

Rebuildable means that git (by commit SHA), GitHub or PyPI can make the part again. Unique means
that only a backup can bring it back. Every part lives on the VM's disk, so the nightly VM backup
holds all of them; the last column says what else exists.

| Part | Where it lives | Kind | Backup |
|---|---|---|---|
| Database | PostgreSQL container `core_postgres_db`, volume `core_postgres_data` (`docker-compose.yml`) | unique | nightly VM backup; also a dump `/opt/core/backups/<stamp>-pre-<sha12>.dump` before each deploy that migrates |
| Vector store | Qdrant (`QDRANT_URL` in `/opt/core/etc/core.env`; `/mnt/vector_db/core_qdrant_db` in compose) | probably derived | in the nightly VM backup only if its storage is on the VM's disk; contents not checked, no verified rebuild ([#1081](https://github.com/DariuszNewecki/CORE/issues/1081)) |
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
| On-disk history | `/opt/dev/CORE/var/law-proposals/`, `/var/lib/core-pipeline/logs/`, `/opt/dev/CORE/.intent/keys/` | unique | nightly VM backup |
| Releases | `/opt/core/releases/<sha>/`, `/opt/core/current` | rebuildable | core-deploy builds them by SHA |
| Custodian venv | `/opt/core-law/venv` | rebuildable | core-law-setup installs it from the live release (its second run on a fresh host) |
| Service units | core's user units in `~core/.config/systemd/user/` (sources in `infra/systemd/d2/`); system units in `/etc/systemd/system/`: the sandbox units (`infra/systemd/sandbox/`), the pipeline and law timers (generated by `infra/core-one-path-setup` and `infra/core-law-setup`) | rebuildable | the setup scripts write them |
| Accounts | `core`, `core-claude`, `core-darek`, group `core-dev` (no script creates them); `core-law`, `core-runner`, `core-build`, `core-sandbox`, group `core-gov` (the setup scripts create them) | rebuildable | listed here |

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
   - `/opt/dev/CORE/var/law-proposals/`, `/var/lib/core-pipeline/`.
3. Record the live commit (`readlink /opt/core/current`) and, for the check at the end, the
   pre-drill state:
   - `sha256sum /opt/core/custody/ledger.jsonl`;
   - `git -C /opt/dev/CORE rev-parse HEAD`;
   - the open-findings count from `core-admin runtime health`.
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
| 6 | Start Qdrant (`docker compose up -d qdrant`), or point `QDRANT_URL` at the existing store. Rebuilding its collections is not documented yet ([#1081](https://github.com/DariuszNewecki/CORE/issues/1081)) | host admin (darek, outside CORE) |
| 7 | Restore `/opt/core-law/home/.ssh/`, `/opt/core/law/private-names/` and `/opt/core/custody/` from the backup. Then `sudo /opt/dev/CORE/infra/core-law-setup --governor core-darek`, first without `--apply` (plan only), then with `--apply`: it creates `core-law`, seeds the release law `/opt/core/law/.intent` and `.specs` from the dev tree, and keeps the restored key and private-names config. Nothing is deployed yet, so it skips the custodian venv and its timers ([#1085](https://github.com/DariuszNewecki/CORE/issues/1085)) | host admin (darek, outside CORE) runs it; core-law then owns the law |
| 8 | `sudo /opt/dev/CORE/infra/core-runtime-setup --ref <sha> --governor core-darek`, first without `--apply` (plan only), then with `--apply`. Then restore `/opt/core/etc/secrets.env`, `deploy.conf` and `core.env` from the backup over the files it made | host admin (darek, outside CORE) |
| 9 | `sudo core-deploy <sha>` (core-runtime-setup installed it): builds the release, switches `/opt/core/current`, starts the services | host admin (darek, outside CORE) runs it; the units then run as `core` |
| 10 | `sudo /opt/dev/CORE/infra/core-law-setup --governor core-darek --apply` again: it installs the custodian venv from the live release and the law timers | host admin (darek, outside CORE) |
| 11 | `sudo bash /opt/dev/CORE/infra/core-one-path-setup --ref <sha>`: the pipeline account, `/etc/core/pipeline.conf`, the timer, `BACKUP_COMMAND` if missing. Restore `/etc/core/pipeline-github-token` if one is used | host admin (darek, outside CORE) runs it; the timer runs as `core-runner` |
| 12 | Restore `/opt/core/deploy-ledger.jsonl`, `/opt/dev/CORE/var/law-proposals/` and `/var/lib/core-pipeline/` from the backup | host admin (darek, outside CORE) |
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
| Database | `core-admin database status` | exit 0 (current) |
| API | `curl http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| Workers | `curl http://127.0.0.1:8000/v1/daemon/status` | every worker alive, recent heartbeat |
| Services | `systemctl --user -M core@ status core-daemon core-api 'core-daemon-worker@*'` and `systemctl status core-sandbox.socket core-pipeline.timer core-law-auto-apply.timer core-law-digest.timer` | all active |
| Sandbox | `sudo runuser -u core -- bash -c 'set -a; . /opt/core/etc/core.env; /opt/core/current/venv/bin/core-admin runtime sandbox-check --mode service'` | every row `passed` |
| Pipeline | `core-admin runtime status` | the recorded commit is live |
| Same state as before | `sha256sum /opt/core/custody/ledger.jsonl`, `git -C /opt/dev/CORE rev-parse HEAD`, the open-findings count from `core-admin runtime health` | equal to the values recorded at backup time |
