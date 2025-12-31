# Local Infrastructure for CORE

## Context

CORE is designed as a local-first governance and enforcement system.
By design, it avoids reliance on external cloud-hosted LLM APIs for
auditability, reproducibility, and data sovereignty reasons.

## Current Situation (As-Is)

- Platform: HP Z420 workstation
- Hypervisor: Proxmox VE (Debian 12)
- GPU: NVIDIA GTX 1050 (2 GB VRAM)
- Storage: SATA SSD + ZFS HDD pool
- Status: Stable, but local inference is impractical

While the current platform remains operational and reliable, enabling
meaningful local inference would require incremental upgrades
(GPU, PSU, NVMe adapters) whose cost and complexity do not carry forward
to a modern, forward-compatible setup.

## Decision

Rather than investing in transitional upgrades around legacy platform
constraints, the project targets a single, bounded replacement platform
that can support local inference for the coming years.

This approach reduces risk, avoids sunk cost, and simplifies long-term
maintenance while preserving a local-first execution model.

## Target Platform (To-Be)

| Component | Target |
|---------|--------|
| CPU | Modern x86 CPU with ~20 cores, strong single-core performance |
| Memory | **64 GB DDR5 ECC** |
| GPU | **NVIDIA RTX 4500 Ada (24 GB VRAM)** |
| Storage | **NVMe SSD (1 TB)** + optional bulk storage |
| OS / Hypervisor | **Proxmox VE** |
| Goal | Practical, sustained local LLM inference |

This is **not** a high-end or aspirational system, but a
minimum viable professional platform for local governance workloads.

## Funding Scope

To keep infrastructure decisions transparent, any funding is limited to:

- hardware required to enable local inference
- infrastructure sustainability (e.g. Proxmox subscription)

Funding explicitly does **not** cover:

- cloud compute or hosted APIs
- SaaS tools
- personal income or consulting
