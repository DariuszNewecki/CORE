# GitHub Status Report — DariuszNewecki/CORE

Generated: 2025-08-18 09:07:35Z

## Repository
{
  "name": "CORE",
  "visibility": "public",
  "default_branch": "main",
  "open_issues_count": 15,
  "description": "The last developer you’ll ever need."
}

## Milestones
{
  "number": 10,
  "title": "v0.6: Operational Hardening & Governance Maturity",
  "state": "open",
  "due_on": null,
  "open_issues": 0,
  "closed_issues": 3,
  "description": "**Goal:** Implement the high-priority \"Tier 2\" recommendations from the AI Peer Review Board.\n\nThis phase focuses on transforming the CORE constitution from a set of rules for code into a complete governance framework for a real-world, operational project.\n\n**Key Objectives:**\n1.  Formalize and define all policy enforcement levels.\n2.  Implement critical new policies for Data Privacy, Secrets Management, and Incident Response.\n3.  Formally document the lifecycle and procedures for human operators."
}
{
  "number": 1,
  "title": "v0.2: Proposal Format & Drift",
  "state": "open",
  "due_on": "2025-09-15T07:00:00Z",
  "open_issues": 1,
  "closed_issues": 4,
  "description": "Purpose:\nNormalize amendment proposals, enforce schema, and surface proposal drift clearly in audits.\nGoal: Normalize proposal formats and eliminate documentation drift around .intent/proposals/* so governance is predictable.\nScope:\n\nLock proposal format with proposal.schema.json (required fields, signatures, rollback hints).\n\nAdd robust auditor checks for proposal schema + “pending summary.”\n\nAdd drift checks (proposal token ≠ current content; missing critical metadata).\n\nUpdate docs & examples; provide a golden sample.\nDone when:\n\nAuditor shows ✅ or actionable ❌ for every proposal, with file paths.\n\nA sample proposal passes end-to-end (sign → canary → approve).\n\nCONTRIBUTING.md and GOVERNANCE docs reference the new format."
}
{
  "number": 7,
  "title": "v0.3: Modular Manifests",
  "state": "open",
  "due_on": "2025-10-25T07:00:00Z",
  "open_issues": 1,
  "closed_issues": 3,
  "description": "Goal: Scale .intent by splitting project_manifest.yaml into per-domain manifests (e.g., src/agents/manifest.yaml, src/system/manifest.yaml).\nScope:\n\nAggregator to produce an in-memory global view.\n\nAuditor reads aggregated view only.\n\nBackward compatible (monolith accepted but discouraged).\nDone when:\n\nAll current data moved to per-domain files.\n\nAuditor passes with only aggregated view.\n\nDocs describe the pattern + migration notes."
}
{
  "number": 8,
  "title": "v0.4: BYOR (Bring Your Own Repo) Ingestion Isomorphism",
  "state": "open",
  "due_on": "2025-11-30T08:00:00Z",
  "open_issues": 1,
  "closed_issues": 3,
  "description": "Goal: Treat any external repo as a first-class citizen. CORE should infer structure, generate a starter .intent, and run a safe audit without modifying the target by default.\nScope:\n\n“BYOR init” command (dry-run and write modes).\n\nKnowledgeGraphBuilder: resilient scanning of unknown layouts.\n\nStarter .intent scaffold + guard rails.\nDone when:\n\nPointing CORE at a repo produces a minimal, valid .intent/ and a readable audit report.\n\nCORE can bootstrap itself via the same path."
}
{
  "number": 9,
  "title": "v0.5: CORE-fication Pipeline & Starter Kits",
  "state": "open",
  "due_on": "2026-01-31T08:00:00Z",
  "open_issues": 1,
  "closed_issues": 2,
  "description": "Goal: Provide first-class scaffolding and pipelines to create new “Mind/Body” apps or CORE-fy existing ones, with optional multi-repo mode.\nScope:\n\ncore-admin new --app <name> scaffolds two modes: single-repo and dual-repo (mind/body separated repos).\n\nPolicy bundles per risk level (low/med/high).\n\nOpinionated logging and tests baked in.\nDone when:\n\nOne command yields a runnable app with docs + CI that passes an initial auditor run."
}

## Open Issues
{
  "number": 30,
  "title": "❌ Nightly Constitutional Audit failed",
  "milestone": null,
  "labels": [
    "ci",
    "audit"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/30",
  "createdAt": "2025-08-16T03:20:13Z"
}
{
  "number": 27,
  "title": "[Refactor] Consolidate Duplicated Logic to Uphold 'dry_by_design' Principle",
  "milestone": null,
  "labels": [
    "priority:high",
    "area:refactoring"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/27",
  "createdAt": "2025-08-12T15:14:17Z"
}
{
  "number": 22,
  "title": "Templates: logging + tests + health endpoints",
  "milestone": "v0.5: CORE-fication Pipeline & Starter Kits",
  "labels": [
    "size:M",
    "priority:medium",
    "type:tooling",
    "area:devx"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/22",
  "createdAt": "2025-08-09T10:55:17Z"
}
{
  "number": 17,
  "title": "KnowledgeGraphBuilder: unknown-layout heuristics",
  "milestone": "v0.4: BYOR (Bring Your Own Repo) Ingestion Isomorphism",
  "labels": [
    "priority:high",
    "size:M",
    "type:tooling",
    "area:introspection"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/17",
  "createdAt": "2025-08-09T10:53:05Z"
}
{
  "number": 14,
  "title": "Docs: Modular manifests guide + examples",
  "milestone": "v0.3: Modular Manifests",
  "labels": [
    "size:S",
    "type:docs",
    "priority:medium"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/14",
  "createdAt": "2025-08-09T10:51:08Z"
}
{
  "number": 9,
  "title": "CLI: core-admin proposals-sample to scaffold golden proposal",
  "milestone": "v0.2: Proposal Format & Drift",
  "labels": [
    "area:governance",
    "size:S",
    "priority:medium",
    "type:cli"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/9",
  "createdAt": "2025-08-09T10:49:31Z"
}
{
  "number": 7,
  "title": "Pilot domain package (proposals)",
  "milestone": null,
  "labels": [
    "roadmap",
    "organizational"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/7",
  "createdAt": "2025-08-09T06:00:34Z"
}
{
  "number": 2,
  "title": "Add JSON logging & request IDs",
  "milestone": null,
  "labels": [
    "roadmap",
    "organizational",
    "type:ci"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/2",
  "createdAt": "2025-08-09T06:00:28Z"
}

## Recently Closed Issues
{
  "number": 29,
  "title": "❌ Nightly Constitutional Audit failed",
  "milestone": null,
  "labels": [
    "ci",
    "audit"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/29",
  "closedAt": "2025-08-15T12:23:04Z"
}
{
  "number": 28,
  "title": "❌ Nightly Constitutional Audit failed",
  "milestone": null,
  "labels": [
    "ci",
    "audit"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/28",
  "closedAt": "2025-08-14T18:32:12Z"
}
{
  "number": 26,
  "title": "[v0.6] EPIC: Implement Critical Operational Policies",
  "milestone": "v0.6: Operational Hardening & Governance Maturity",
  "labels": [
    "type:epic",
    "area:governance"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/26",
  "closedAt": "2025-08-14T18:30:31Z"
}
{
  "number": 25,
  "title": "[v0.6] Formalize Policy Enforcement Levels",
  "milestone": "v0.6: Operational Hardening & Governance Maturity",
  "labels": [
    "area:governance",
    "area:auditor"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/25",
  "closedAt": "2025-08-14T18:28:56Z"
}
{
  "number": 24,
  "title": "[v0.6] Formally Document the Human Operator Lifecycle",
  "milestone": "v0.6: Operational Hardening & Governance Maturity",
  "labels": [
    "area:governance",
    "type:docs"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/24",
  "closedAt": "2025-08-14T18:27:58Z"
}
{
  "number": 23,
  "title": "❌ Nightly Constitutional Audit failed",
  "milestone": null,
  "labels": [
    "ci",
    "audit"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/23",
  "closedAt": "2025-08-12T15:11:18Z"
}
{
  "number": 21,
  "title": "Starter kits: low/med/high risk policy bundles",
  "milestone": "v0.5: CORE-fication Pipeline & Starter Kits",
  "labels": [
    "size:M",
    "priority:medium",
    "type:tooling",
    "area:intent"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/21",
  "closedAt": "2025-08-11T12:19:50Z"
}
{
  "number": 20,
  "title": "CLI: core-admin new (single-repo & dual-repo)",
  "milestone": "v0.5: CORE-fication Pipeline & Starter Kits",
  "labels": [
    "priority:medium",
    "type:cli",
    "size:L",
    "area:scaffolding"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/20",
  "closedAt": "2025-08-11T12:20:36Z"
}
{
  "number": 19,
  "title": "Docs: BYOR quickstart",
  "milestone": "v0.4: BYOR (Bring Your Own Repo) Ingestion Isomorphism",
  "labels": [
    "size:S",
    "type:docs",
    "priority:medium"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/19",
  "closedAt": "2025-08-11T11:29:45Z"
}
{
  "number": 18,
  "title": "Seed .intent template pack",
  "milestone": "v0.4: BYOR (Bring Your Own Repo) Ingestion Isomorphism",
  "labels": [
    "size:M",
    "priority:medium",
    "type:tooling",
    "area:intent"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/18",
  "closedAt": "2025-08-11T11:20:57Z"
}
{
  "number": 16,
  "title": "CLI: core-admin byor-init <path> [--write] [--dry-run]",
  "milestone": "v0.4: BYOR (Bring Your Own Repo) Ingestion Isomorphism",
  "labels": [
    "priority:high",
    "type:cli",
    "size:L",
    "area:ingestion"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/16",
  "closedAt": "2025-08-11T10:12:37Z"
}
{
  "number": 15,
  "title": "Migration tool: split monolithic manifest",
  "milestone": "v0.3: Modular Manifests",
  "labels": [
    "size:M",
    "priority:medium",
    "type:cli",
    "area:intent"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/15",
  "closedAt": "2025-08-10T14:42:03Z"
}
{
  "number": 13,
  "title": "Auditor: consume only aggregated manifest",
  "milestone": "v0.3: Modular Manifests",
  "labels": [
    "area:auditor",
    "priority:high",
    "size:M",
    "type:tooling"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/13",
  "closedAt": "2025-08-11T08:46:12Z"
}
{
  "number": 12,
  "title": "Implement manifest aggregator (per-domain → global)",
  "milestone": "v0.3: Modular Manifests",
  "labels": [
    "priority:high",
    "type:tooling",
    "area:intent",
    "size:L"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/12",
  "closedAt": "2025-08-11T08:45:13Z"
}
{
  "number": 11,
  "title": "CI: validate proposals on PRs",
  "milestone": "v0.2: Proposal Format & Drift",
  "labels": [
    "type:epic",
    "priority:high",
    "size:S"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/11",
  "closedAt": "2025-08-10T14:19:56Z"
}
{
  "number": 10,
  "title": "Docs: add \"Proposals & Canary\" quickstart + sample",
  "milestone": "v0.2: Proposal Format & Drift",
  "labels": [
    "size:S",
    "type:docs",
    "priority:medium"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/10",
  "closedAt": "2025-08-10T14:21:11Z"
}
{
  "number": 8,
  "title": "Auditor: add ProposalChecks (schema + pending summary + drift)",
  "milestone": "v0.2: Proposal Format & Drift",
  "labels": [
    "area:auditor",
    "priority:high",
    "size:M",
    "type:tooling"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/8",
  "closedAt": "2025-08-10T14:14:36Z"
}
{
  "number": 6,
  "title": "Modular manifests (aggregator + fallback)",
  "milestone": null,
  "labels": [
    "roadmap",
    "organizational",
    "type:epic"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/6",
  "closedAt": "2025-08-10T14:42:47Z"
}
{
  "number": 5,
  "title": "Governance: proposal.schema.json + proposal_checks",
  "milestone": "v0.2: Proposal Format & Drift",
  "labels": [
    "roadmap",
    "organizational",
    "area:governance",
    "area:auditor",
    "priority:high",
    "size:M",
    "type:tooling"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/5",
  "closedAt": "2025-08-10T14:21:56Z"
}
{
  "number": 4,
  "title": "Docs: CONVENTIONS.md & DEPENDENCIES.md",
  "milestone": null,
  "labels": [
    "roadmap",
    "organizational",
    "type:docs"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/4",
  "closedAt": "2025-08-15T12:29:24Z"
}
{
  "number": 3,
  "title": "Pre-commit hooks (Black, Ruff)",
  "milestone": null,
  "labels": [
    "roadmap",
    "organizational",
    "type:ci"
  ],
  "url": "https://github.com/DariuszNewecki/CORE/issues/3",
  "closedAt": "2025-08-15T12:28:40Z"
}
{
  "number": 1,
  "title": "[Enhancement] Refactor validation_pipeline to use a unified violations list",
  "milestone": null,
  "labels": [],
  "url": "https://github.com/DariuszNewecki/CORE/issues/1",
  "closedAt": "2025-08-08T14:15:39Z"
}

## Labels
{
  "name": "organizational",
  "color": "a2eeef",
  "description": "Project organization"
}
{
  "name": "roadmap",
  "color": "0366d6",
  "description": "Roadmap item"
}
{
  "name": "type:ci",
  "color": "5319e7",
  "description": "CI/CD"
}
{
  "name": "type:epic",
  "color": "0366d6",
  "description": "Multi-issue epic"
}
{
  "name": "type:vision",
  "color": "6f42c1",
  "description": "Vision/North Star"
}
{
  "name": "type:task",
  "color": "a2eeef",
  "description": "Executable task"
}
{
  "name": "ws:byor",
  "color": "fbca04",
  "description": ""
}
{
  "name": "ws:governance",
  "color": "d73a4a",
  "description": ""
}
{
  "name": "ws:planner",
  "color": "0e8a16",
  "description": ""
}
{
  "name": "ws:validation",
  "color": "c2e0c6",
  "description": ""
}
{
  "name": "area:governance",
  "color": "0366d6",
  "description": ""
}
{
  "name": "area:auditor",
  "color": "0e8a16",
  "description": ""
}
{
  "name": "priority:high",
  "color": "d73a4a",
  "description": ""
}
{
  "name": "size:M",
  "color": "bfdadc",
  "description": ""
}
{
  "name": "size:S",
  "color": "c2e0c6",
  "description": ""
}
{
  "name": "type:docs",
  "color": "0075ca",
  "description": ""
}
{
  "name": "priority:medium",
  "color": "fbca04",
  "description": ""
}
{
  "name": "type:cli",
  "color": "e4e669",
  "description": ""
}
{
  "name": "type:tooling",
  "color": "ededed",
  "description": ""
}
{
  "name": "area:intent",
  "color": "006b75",
  "description": ""
}
{
  "name": "size:L",
  "color": "a2eeef",
  "description": ""
}
{
  "name": "area:ingestion",
  "color": "1f883d",
  "description": ""
}
{
  "name": "area:introspection",
  "color": "5319e7",
  "description": ""
}
{
  "name": "area:scaffolding",
  "color": "8250df",
  "description": ""
}
{
  "name": "area:devx",
  "color": "0969da",
  "description": ""
}
{
  "name": "audit",
  "color": "ededed",
  "description": ""
}
{
  "name": "ci",
  "color": "ededed",
  "description": ""
}
{
  "name": "area:refactoring",
  "color": "305763",
  "description": ""
}
{
  "name": "dependencies",
  "color": "0366d6",
  "description": "Pull requests that update a dependency file"
}
{
  "name": "github_actions",
  "color": "000000",
  "description": "Pull requests that update GitHub Actions code"
}

## Projects (Projects v2)
6	CORE Roadmap	open	PVT_kwHOAxIPlc4BACPl

## Releases
v0.2.0	Latest	v0.2.0	2025-08-15T20:50:16Z

