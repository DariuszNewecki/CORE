#!/usr/bin/env bash
#
# scripts/coldroom-prep.sh — build the CORE "cold-room" VM template.
#
# The cold-room is a freshly-provisioned machine used to verify, from zero, that
# a newcomer can reproduce CORE's full thesis from public artifacts alone:
#   - #561 (docs polish): clone + ./install-core.sh works from public docs
#   - #562 (demo reliability): the consequence-chain demo runs cleanly 3x
#
# This script bakes the PREREQUISITES into a golden image — never CORE itself.
# Every test run does a fresh `git clone` on a linked clone of the template;
# baking CORE would defeat the purpose. See project memory: demo_is_the_onramp.
#
# Target: a fresh Ubuntu 24.04 LTS VM (Python 3.12 native). Run as a sudo user.
#
# Pre-steps done at VM creation (NOT in this script — they bootstrap access):
#   - create a sudo user (e.g. 'core')
#   - install openssh-server; authorize the operator's SSH key
#   - (optional) passwordless sudo for unattended prep:
#       echo '<user> ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/99-<user>
#   - remove cloud-init if present (slow boot): sudo apt-get purge -y cloud-init
#
# Workflow:
#   1. provision Ubuntu 24.04 VM  →  2. run this script  →  3. Proxmox "Convert
#   to Template"  →  4. linked-clone per test  →  5. on the clone:
#        git clone https://github.com/DariuszNewecki/CORE.git && cd CORE && ./install-core.sh
#
# Provenance: derived from the interactive build on 2026-06-14
# (core-coldroom-base @ Ubuntu 24.04). Re-verify versions on next rebuild.
set -euo pipefail

USER_NAME="${SUDO_USER:-$(id -un)}"
QDRANT_IMAGE="qdrant/qdrant:v1.18.0"  # must match docker-compose.yml
PG_IMAGE="postgres:16"                # must match docker-compose.yml

say() { printf '\n\033[1;36m━━ %s ━━\033[0m\n' "$*"; }

# ---- 1. OS up to date ------------------------------------------------------
say "Updating the OS"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
# python3-pip/python3-venv are NOT guaranteed present on a minimal Ubuntu
# 24.04 image/LXC template — confirmed missing on a fresh unprivileged LXC
# 2026-07-12. The Poetry installer below bootstraps its own venv via
# `python3 -m venv`, which fails without python3-venv.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  ca-certificates curl git make python3-pip python3-venv

# ---- 2. Docker (official repo) + rootless-for-user -------------------------
say "Installing Docker + Compose"
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER_NAME"   # rootless docker for the newcomer pattern

# ---- 3. Pre-pull the images install-core.sh will need ----------------------
say "Pre-pulling service images (so 'docker compose up' is instant per clone)"
sudo docker pull -q "$PG_IMAGE"
sudo docker pull -q "$QDRANT_IMAGE"

# ---- 4. Poetry (in-project venv, matching CORE's .venv convention) ---------
say "Installing Poetry"
curl -sSL https://install.python-poetry.org | python3 -
sudo ln -sf "/home/${USER_NAME}/.local/bin/poetry" /usr/local/bin/poetry
poetry config virtualenvs.in-project true   # demo.sh / proof-index use .venv/bin/python

# ---- 5. Template-safe cleanup (run last, just before "Convert to Template") -
say "Template-safe cleanup"
sudo DEBIAN_FRONTEND=noninteractive apt-get autoremove -y -qq || true
sudo apt-get clean
sudo docker rmi hello-world >/dev/null 2>&1 || true
# Unique machine-id per clone (systemd regenerates the empty file on boot):
sudo truncate -s 0 /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id
sudo ln -sf /etc/machine-id /var/lib/dbus/machine-id
# NOTE: SSH host keys are intentionally KEPT so linked clones are reachable
# immediately (acceptable for a throwaway LAN cold-room — clones share host
# keys). To regenerate per clone instead, rm /etc/ssh/ssh_host_*_key here and
# add a first-boot 'ssh-keygen -A' oneshot ordered Before=ssh.service.
sudo journalctl --rotate >/dev/null 2>&1 || true
sudo journalctl --vacuum-time=1s >/dev/null 2>&1 || true
sudo find /var/log -type f -name '*.log' -exec truncate -s 0 {} \; 2>/dev/null || true
cat /dev/null > "$HOME/.bash_history" 2>/dev/null || true

say "READY-FOR-TEMPLATE — stop the VM and convert it to a template"
