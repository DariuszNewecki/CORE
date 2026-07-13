---
kind: planning
title: VM SSH Access — Internal Runbook for core-cli Smoke Testing
status: accepted
---

# VM SSH Access — Internal Runbook for core-cli Smoke Testing

Procedure for getting Claude Code SSH access to a test VM before running a
core-cli deployment/smoke test. Written after `.46` → `.48` churn wasted a
session on ad-hoc guessing.

---

## Steps

1. **Check host online.** `nc -z -w5 <ip> 22` (or `ssh ... -o ConnectTimeout=5`).
   Retry a few times before declaring it down — DHCP/boot lag is normal.

2. **Trust the SSH host key.** `ssh-keyscan -T 5 <ip> >> ~/.ssh/known_hosts`,
   then show the fingerprint (`ssh-keygen -F <ip> -f ~/.ssh/known_hosts -l`)
   for the governor to eyeball before anything else touches the host.

3. **Governor provisions access.** On the VM (via whatever access the
   governor already has — console, cloud-init, etc.), run:
   ```bash
   sudo useradd -m -s /bin/bash core-cli
   sudo mkdir -p /home/core-cli/.ssh
   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN2O2L5F6ZV1qmVRQkXYgWNDV+HqPJMPqx4a582Geopi claude-code-core-cli-smoke-test-persistent' | sudo tee /home/core-cli/.ssh/authorized_keys
   sudo chown -R core-cli:core-cli /home/core-cli/.ssh
   sudo chmod 700 /home/core-cli/.ssh && sudo chmod 600 /home/core-cli/.ssh/authorized_keys
   ```
   Reuses the existing persistent key (`~/.ssh/core_cli_smoke`, generated
   2026-07-12) — no new key per VM.

4. **Verify access.** `ssh -o BatchMode=yes -i ~/.ssh/core_cli_smoke core-cli@<ip> "whoami && hostname"`.
   Stop and report on any failure — no guessing at alternate users/passwords.

5. **Run the test**, following `docs/byor-quickstart.md` / the smoke-test
   doc's procedure. Record results in
   `.specs/planning/CORE-CLI-Release-Smoke-Test.md` or the relevant
   followups doc.
