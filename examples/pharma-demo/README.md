# Pharma Demo — GRC Gap Analysis (PROJ-26.001)

Synthetic pharma compliance corpus for demonstrating CORE's GRC gap-analysis service against the 21 CFR Part 11 and EU Annex 11 catalogs.

## What this is

Seven realistic but synthetic GxP compliance documents representing a fictional contract manufacturing organisation (PharmaCo Ltd). Documents are designed to produce a representative mix of verdicts across both catalogs — not a pass parade; real gaps are intentional.

## Corpus

| File | Document | Key Coverage |
|---|---|---|
| `csv-policy.md` | Computer System Validation Policy | §11.10(a) validation, Annex 11 §4 |
| `electronic-records-sop.md` | Electronic Records & Data Integrity SOP | §11.10 closed systems, Annex 11 §5 data checks |
| `electronic-signature-policy.md` | Electronic Signature Policy | §11.50 manifestations*, §11.200 components, Annex 11 §14 |
| `access-control-sop.md` | Access Control & Password Management SOP | §11.300 passwords, Annex 11 §12 security |
| `audit-trail-review-sop.md` | Audit Trail Review Procedure | §11.10(e) timestamps, Annex 11 §9 audit trails |
| `data-backup-sop.md` | Data Backup & Storage Security SOP | Annex 11 §7 data storage† |
| `training-qualification-sop.md` | Personnel Training & Qualification SOP | §11.10(i) training |

\* §11.50 gap: signature manifestations mention signer name and meaning but omit the date and time of signing.
† Annex 11 §7 gap: backup SOP addresses frequency and media protection but does not require explicit restore-capability testing.

### Intentional gaps for demo realism

- **§11.70 (signature/record linking)** — not addressed by any document → NOT_COVERED
- **§11.50 (signature manifestations)** — date/time of signing omitted → DEFICIENT
- **Annex 11 §7 (data storage)** — restore testing not required → DEFICIENT
- **Attestation requirements** (§11.10(a), §11.10(i), §11.100(c), Annex 11 §1, §11, §16) → NEEDS_HUMAN by design (irreducibly human controls)

## Running the demo

```bash
# Gap analysis against 21 CFR Part 11
core-admin grc gap-analysis examples/pharma-demo/corpus --catalog cfr_part_11

# Gap analysis against EU Annex 11
core-admin grc gap-analysis examples/pharma-demo/corpus --catalog eu_annex_11

# Both catalogs in one pass (multi-catalog mode)
core-admin grc gap-analysis examples/pharma-demo/corpus --catalog cfr_part_11 --catalog eu_annex_11

# Skip applicability confirmation (corpus is clearly pharma-domain)
core-admin grc gap-analysis examples/pharma-demo/corpus --catalog cfr_part_11 --assume-applicable

# Write YAML report to var/reports/
core-admin grc gap-analysis examples/pharma-demo/corpus --catalog cfr_part_11 --write
```

## Expected verdicts (approximate — LLM verdicts may vary by model/session)

### 21 CFR Part 11

| Requirement | Expected | Driver |
|---|---|---|
| `cfr_part_11.doc_finalized` | SATISFIED | No TBD/TODO/DRAFT in any document |
| `cfr_part_11.11_10_closed_system_controls` | SATISFIED | `electronic-records-sop.md` §3 |
| `cfr_part_11.11_10_audit_trail` | SATISFIED | `audit-trail-review-sop.md` §3.1–3.2 |
| `cfr_part_11.11_50_signature_manifestations` | DEFICIENT | Date/time of signing absent from `electronic-signature-policy.md` §3.3 |
| `cfr_part_11.11_70_signature_record_linking` | NOT_COVERED | No document addresses record-linking permanence |
| `cfr_part_11.11_200_signature_components` | SATISFIED | `electronic-signature-policy.md` §3.2 |
| `cfr_part_11.11_300_password_controls` | SATISFIED | `access-control-sop.md` §4 |
| `cfr_part_11.11_10a_validation` | NEEDS_HUMAN | Attestation gate |
| `cfr_part_11.11_10i_training` | NEEDS_HUMAN | Attestation gate |
| `cfr_part_11.11_100_signer_certification` | NEEDS_HUMAN | Attestation gate |

### EU Annex 11

| Requirement | Expected | Driver |
|---|---|---|
| `eu_annex_11.doc_finalized` | SATISFIED | No TBD/TODO/DRAFT in any document |
| `eu_annex_11.4_validation` | SATISFIED | `csv-policy.md` §3.1–3.4 |
| `eu_annex_11.5_data` | SATISFIED | `electronic-records-sop.md` §3.3 |
| `eu_annex_11.7_data_storage` | DEFICIENT | `data-backup-sop.md` addresses backup and media but not restore-capability testing |
| `eu_annex_11.9_audit_trails` | SATISFIED | `audit-trail-review-sop.md` §4 |
| `eu_annex_11.12_security` | SATISFIED | `access-control-sop.md` §3 |
| `eu_annex_11.14_electronic_signature` | SATISFIED | `electronic-signature-policy.md` §3.1 |
| `eu_annex_11.1_risk_management` | NEEDS_HUMAN | Attestation gate |
| `eu_annex_11.11_periodic_evaluation` | NEEDS_HUMAN | Attestation gate |
| `eu_annex_11.16_business_continuity` | NEEDS_HUMAN | Attestation gate |

## Summary profile

A mature but not perfect compliance posture — realistic for an organisation midway through a GxP programme uplift. The corpus covers the main technical and process controls; gaps are specific and remediable, not systemic.

## Note on LLM availability

If `core-api` is running but the LLM is unavailable, judged requirements return `UNAVAILABLE` rather than a false verdict. This is intentional — CORE does not sell silence as compliance. Re-run when the cognitive service is online to get full verdicts.
