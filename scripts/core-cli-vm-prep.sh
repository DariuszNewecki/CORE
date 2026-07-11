#!/usr/bin/env bash
#
# scripts/core-cli-vm-prep.sh — prep a minimal VM/container for the core-cli
# release smoke test (.specs/planning/CORE-CLI-Release-Smoke-Test.md).
#
# Unlike scripts/coldroom-prep.sh (which bakes in Docker + Postgres + Qdrant to
# run the full CORE stack for the install-from-scratch demo, #562), this test
# only installs the core-cli pip package and talks to an already-running CORE
# instance over HTTP. No database, no container runtime, no CORE source on the
# box at all.
#
# Target: a fresh Ubuntu 24.04 LTS VM or container, Python 3.12 native. Run as
# a sudo user. Proven sufficient on a Proxmox unprivileged LXC container at
# 2 vCPU / 4GiB RAM / 512MiB swap / 8GiB disk — see the smoke test doc's
# "VM tech specs" section for the source of these numbers.
#
# Pre-steps done at VM/container creation (NOT in this script — they bootstrap
# access):
#   - create a sudo user (e.g. 'core')
#   - install openssh-server; authorize the operator's SSH key
#   - (optional) passwordless sudo for unattended prep:
#       echo '<user> ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/99-<user>
#
# Workflow:
#   1. provision Ubuntu 24.04 VM/container  →  2. run this script  →
#   3. hand SSH access to Claude Code  →  4. run the smoke test doc's phases
#
# Re-verify versions on next rebuild.
set -euo pipefail

say() { printf '\n\033[1;36m━━ %s ━━\033[0m\n' "$*"; }

# ---- 1. OS up to date -------------------------------------------------------
say "Updating the OS"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl git

# ---- 2. Python 3.12 + venv ---------------------------------------------------
say "Installing Python 3.12"
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12 python3.12-venv

say "Verifying Python version"
python3.12 --version

say "READY — hand SSH access to Claude Code and proceed with the smoke test doc"
