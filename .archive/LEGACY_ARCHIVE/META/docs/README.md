CORE .intent/ META Layer
Purpose

The .intent/ directory is the Constitution of CORE.

Everything under .intent/ is active, authoritative, and binding by definition.
There is no lifecycle state, no enable/disable flag, and no implicit defaults.

The META layer defines the structure of law, not the law itself.

Design Principles

Single source of structural truth
All .intent/ documents are validated against schemas defined in .intent/META/.

No static index
CORE discovers intent dynamically by reading the filesystem.
META defines allowed shapes, not enumerations of files.

LLM-readable by design
Structures are explicit, normalized, and self-describing.
No implicit conventions, no hidden coupling.

Schemas are tools, not law
Schema files do not carry governance metadata (owners, review cadence, status).
Only documents validated by schemas are governed artifacts.

META Directory Structure
.intent/META/
├── header.schema.json
├── rule.schema.json
├── policy.schema.json
├── standard.schema.json
├── precedence.schema.json
├── registry.schema.json
├── META-SCHEMA.json
└── docs/
    └── README.md   ← this file


Only foundational schemas live here.
There must be no nested META directories elsewhere in .intent/.

Core META Schemas
header.schema.json

Defines the mandatory document header shared by all intent documents.

Every .intent/**/*.json document MUST:

define identity (id, version, title)

declare ownership (owners)

define review cadence (review)

declare its logical kind (type)

declare the validating schema (schema_id)

The header is never redefined elsewhere.

rule.schema.json

Defines the structure of a single enforceable rule.

Rules:

are atomic

have a clear statement and rationale

declare enforcement strength

declare an execution engine (check.engine)

never contain policy aggregation logic

Rules are contained by policies or standards.

policy.schema.json

Defines a policy document.

Policies:

aggregate rules

define scope of applicability

express enforceable law

contain no execution logic

Policies are the primary enforcement units.

standard.schema.json

Defines a standard document.

Standards:

provide guidance and best practices

may optionally include enforceable rules

are advisory-first, enforcement-second

Standards may evolve without changing policy semantics.

precedence.schema.json

Defines conflict resolution rules.

Precedence documents:

define hierarchy between policies

resolve conflicts deterministically

never embed enforcement logic

Lower level number = higher authority.

registry.schema.json

Defines the allowed intent domains.

This is not a static registry.

It declares:

what kinds of intent domains may exist

how CORE may classify discovered intent

Actual activation is determined by files on disk.

META-SCHEMA.json

Defines the meta-rules for META itself.

It enforces:

separation of schema vs law

correct header usage

allowed META document types

structural invariants

This schema exists to prevent META drift.

What META Explicitly Does NOT Do

No execution semantics

No engine configuration

No runtime defaults

No lifecycle management

No implicit behavior

META answers only one question:

“What shape must valid intent take?”

Enforcement Model

CORE loads .intent/ dynamically

Documents are validated against META schemas

Invalid documents are rejected

Enforcement engines interpret valid intent

META is pre-runtime, static, and absolute.

Stability Contract

Changes to .intent/META/ are:

rare

deliberate

breaking by default

If META changes, downstream intent must be refactored.

This is intentional.

Audience

This layer is written for:

Governance maintainers

CORE developers

LLMs reasoning about CORE

If a reader cannot understand intent structure by reading META, META is wrong.