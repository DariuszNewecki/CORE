# ADR-059 — Severity Vocabulary Governance

**Date:** 2026-05-19
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** open governor decisions from ADR-056 Wave 1 session (2026-05-19)
**Related:** ADR-056 (runtime data contracts), ADR-015 (consequence chain attribution)

---

## Context

ADR-056 Wave 1 introduced governed JSON Schemas for the consequence chain,
universal result family, and AI invocation surface. It also introduced
thirteen vocabulary enums in `.intent/META/enums.json`. During Wave 1
authoring, three vocabulary decisions were deferred to the governor:

1. `RiskAssessment.overall_risk` uses the value "dangerous" in Python
   (`src/will/autonomy/proposal.py`). The governed `proposal_risk` enum
   uses "high" as the top value. The two surfaces are out of alignment.

2. `AuditFinding.AuditSeverity` in Python (`src/shared/models/audit_models.py`)
   carries a three-value set: INFO / WARNING / ERROR. This mirrors syslog
   log-level vocabulary, not finding severity vocabulary. The governed
   `audit_severity` enum in `enums.json` currently mirrors the Python class
   and therefore inherits the same wrong vocabulary. A five-value finding
   severity scale (INFO / LOW / MEDIUM / HIGH / BLOCK) is already in use on
   the CIM surface (`src/body/services/cim/models.py`) and is the correct
   scale for audit findings.

3. Across all severity-adjacent surfaces in CORE there are five distinct
   enumerations and three distinct value sets. No documented principle exists
   to determine whether these should be unified or kept separate, and what
   the translation rules are at cross-domain boundaries.

All three decisions are governor vocabulary decisions. They cannot be resolved
by convention or code inspection alone. This ADR records the decisions and
establishes the canonical vocabulary for each domain.

---

## Decisions

### D1 — Retire "dangerous"; align `RiskAssessment.overall_risk` to `proposal_risk`

The value "dangerous" is not a standard risk classification term in any
recognised risk management framework (ISO 31000, ICH Q9, NIST SP 800-30).
It is an adjective describing a state, not an ordinal risk level.

The governed `proposal_risk` enum already carries "high" as the correct
top-level risk value. "Dangerous" and "high" name the same level with
inconsistent vocabulary.

**Decision:** "dangerous" is retired. `RiskAssessment.overall_risk` MUST
use values drawn exclusively from the `proposal_risk` enum:
`safe | moderate | high`.

The Python implementation in `compute_risk()` replaces "dangerous" with
"high" throughout: in the `risk_levels` dict, the derivation array, and
all conditional branches that test for "dangerous".

The `proposal_risk` enum in `enums.json` is authoritative and unchanged.
`RiskAssessment.schema.json` MUST reference it via `$ref` for the
`overall_risk` field.

If a fourth risk level above "high" is needed in future, the canonical
term is "critical" (consistent with `risk_tier` and ICH Q9). "Dangerous"
MUST NOT be reintroduced.

---

### D2 — Retire the three-value audit severity set; adopt the five-value finding severity scale

The three-value set INFO / WARNING / ERROR is syslog vocabulary. ERROR
in that vocabulary means "the instrument failed to produce output," not
"this finding is severe." Applied to audit findings it conflates
instrument health with finding severity and produces a scale with no
actionable ceiling.

The five-value scale INFO / LOW / MEDIUM / HIGH / BLOCK is a proper
finding severity scale. BLOCK is the actionable ceiling: a finding at
this level halts execution. The scale is already in use on the CIM
surface and matches static-analysis industry practice (SonarQube, CVSS
tiers, GxP audit severity classification).

**Decision:** The `audit_severity` enum in `enums.json` is replaced:

```json
"audit_severity": {
  "description": "Severity levels for audit findings. BLOCK halts execution. HIGH/MEDIUM/LOW are actionable at decreasing urgency. INFO is informational only. Governed by ADR-059. Python source: src/shared/models/audit_models.py AuditSeverity.",
  "type": "string",
  "enum": ["info", "low", "medium", "high", "block"]
}
```

The Python `AuditSeverity` class in `src/shared/models/audit_models.py`
is updated from `INFO / WARNING / ERROR` to `INFO / LOW / MEDIUM / HIGH /
BLOCK`. All call sites that reference `AuditSeverity.WARNING` or
`AuditSeverity.ERROR` are migrated to the new vocabulary. The CIM surface
(`Literal['BLOCK', 'HIGH', 'MEDIUM', 'LOW', 'INFO']`) is aligned to
lowercase string form, consistent with the governed enum.

The three-value set INFO / WARNING / ERROR is retired from governance
artifacts. It MAY continue to exist in operational logging infrastructure
(Python `logging` module levels) where it carries its original syslog
meaning and serves a different consumer.

`AuditFinding.schema.json` MUST reference `audit_severity` via `$ref`
for the `severity` field.

---

### D3 — Severity surfaces are distinct domains; no unification; translation rules defined at boundaries

CORE has five severity-adjacent enumerations across three distinct domains:

| Domain | Enum | Values | Consumer |
|---|---|---|---|
| Audit findings | `audit_severity` | info / low / medium / high / block | Audit engine — governs pass / fail / block decisions |
| Proposal risk | `proposal_risk` | safe / moderate / high | Proposal approval gate — governs `approval_required` |
| Validator input | `risk_tier` | routine / standard / elevated / critical | Constitutional validator — pre-decision risk classification |
| Log levels | *(not a governed enum)* | INFO / WARNING / ERROR | Python `logging` — operational observability |
| CIM finding | *(governed by D2 above)* | aligned to `audit_severity` post-D2 | CIM policy engine output |

**Decision:** These are three distinct domains serving distinct consumers
at distinct points in the governance lifecycle. They MUST NOT be unified
into a single enum. A unified scale would serve no consumer well and
would conflate execution-gating semantics (BLOCK) with approval-routing
semantics (safe → auto-approve) and risk-input semantics (routine →
minimal validation).

Translation rules at the two load-bearing cross-domain boundaries are
defined here as constitutional policy:

**Boundary 1 — `risk_tier` → `proposal_risk`** (validator input → proposal
self-assessment, used in approval routing):

| risk_tier | proposal_risk |
|---|---|
| critical | high |
| elevated | high |
| standard | moderate |
| routine | safe |

**Boundary 2 — `audit_severity` → log level** (finding severity → operational
log output):

| audit_severity | log level |
|---|---|
| block | ERROR |
| high | ERROR |
| medium | WARNING |
| low | INFO |
| info | INFO |

These translation rules are constitutional. Any implementation that
crosses these boundaries MUST follow the table above. Deviations require
a successor ADR.

---

## `.intent/` consequences

| Artifact | Change |
|---|---|
| `.intent/META/enums.json` | Replace `audit_severity` value set with 5-value scale per D2 |
| `.intent/enforcement/contracts/RiskAssessment.schema.json` | `overall_risk` field `$ref`s `proposal_risk` enum |
| `.intent/enforcement/contracts/AuditFinding.schema.json` | `severity` field `$ref`s `audit_severity` enum |

---

## Python consequences

| File | Change |
|---|---|
| `src/shared/models/audit_models.py` | `AuditSeverity` — replace INFO/WARNING/ERROR with INFO/LOW/MEDIUM/HIGH/BLOCK |
| `src/will/autonomy/proposal.py` | `compute_risk()` — replace "dangerous" with "high" throughout |
| All call sites of `AuditSeverity.WARNING` / `AuditSeverity.ERROR` | Migrate to new vocabulary |

---

## Consequences

**Positive:**

- All three open governor decisions from ADR-056 Wave 1 are resolved and
  recorded as constitutional policy.
- `RiskAssessment.overall_risk` and `proposal_risk` are now the same
  vocabulary. Contract enforcement via JSON Schema `$ref` is now
  mechanically sound — no value can appear in one surface that is absent
  from the governed enum.
- `audit_severity` now carries finding-severity semantics rather than
  syslog semantics. BLOCK is a constitutional concept, not an ad-hoc
  string. GxP audit classification aligns directly to this scale.
- The three-domain principle gives future engineers a documented decision
  surface: when adding a new severity-adjacent enum, the first question
  is "which domain does this serve?" — not "how does this fit the one big
  scale?"
- Translation tables are constitutional. Cross-domain boundary code has
  a verifiable specification to implement against.

**Negative:**

- `AuditSeverity.WARNING` and `AuditSeverity.ERROR` are retired. Call-site
  migration is a mechanical rename but requires full grep coverage to avoid
  silent breakage. Missed sites will fail at runtime with `AttributeError`,
  not at audit time — until a contract rule is added for Python enum
  vocabulary conformance (tracked separately).
- The CIM surface uses uppercase string literals today. D2 aligns it to
  lowercase. Any serialised CIM output stored in the DB before this change
  carries uppercase values. Whether that constitutes a migration hazard
  depends on whether those values are round-tripped through `audit_severity`
  validation — to be confirmed during implementation.

---

## Verification

This ADR is verified when:

1. `enums.json` `audit_severity` contains exactly `["info", "low", "medium", "high", "block"]`.
2. `RiskAssessment.schema.json` `overall_risk` field carries `"$ref": "#/definitions/proposal_risk"` (or equivalent path).
3. `AuditFinding.schema.json` `severity` field carries `"$ref": "#/definitions/audit_severity"` (or equivalent path).
4. `grep -rn '"dangerous"' src/will/autonomy/proposal.py` returns zero hits.
5. `grep -rn 'AuditSeverity.WARNING\|AuditSeverity.ERROR' src/` returns zero hits (excluding test fixtures, if any).
6. `core-admin code audit` PASS; finding count does not increase beyond baseline.

---

## References

- ADR-056 — Runtime data contracts; D5 introduced `enums.json`; D7 boundary criteria govern when schemas are required
- ADR-015 — Consequence chain attribution; `approval_authority` non-omittable governance
- `.intent/META/enums.json` — canonical vocabulary store; `proposal_risk`, `audit_severity`, `risk_tier` entries
- `src/will/autonomy/proposal.py:78` — `RiskAssessment` dataclass and `compute_risk()` implementation
- `src/shared/models/audit_models.py:14` — `AuditSeverity` IntEnum (pre-ADR state: INFO/WARNING/ERROR)
- `src/body/services/cim/models.py:283` — CIM Pydantic Finding (pre-ADR state: uppercase BLOCK/HIGH/MEDIUM/LOW/INFO)
- ISO 31000 — Risk management vocabulary (low/medium/high/critical ordinal)
- ICH Q9 — Quality risk management (pharma GxP; severity/probability/detectability matrix)
