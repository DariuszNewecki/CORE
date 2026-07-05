# Audit Trail Review Procedure

**Document ID:** SYS-SOP-005
**Version:** 1.6
**Effective Date:** 2026-02-10
**Owner:** QA Manager, Data Integrity
**Classification:** GxP Controlled Document

---

## 1. Purpose

This SOP defines the requirements for the generation, protection, and periodic review of audit trails within GxP computerised systems at PharmaCo Ltd. Audit trails are a fundamental data integrity control, providing a chronological record of user activity that supports reconstruction of any data change.

## 2. Scope

This SOP applies to all GxP computerised systems that generate audit trail records, and to the personnel responsible for reviewing those records.

## 3. Audit Trail Generation Requirements

### 3.1 System-Generated Records

Audit trails shall be system-generated automatically. Manual audit trail entries are not permitted. Each audit trail entry shall capture at minimum:

- Date and time of the action (system clock, synchronised to a time server)
- User ID of the operator performing the action
- The nature of the action (creation, modification, deletion)
- The original value (before modification) and the new value (after modification) for each changed field
- The reason for change, where the system supports a mandatory "reason for change" field

The system clock shall be validated as part of IQ and confirmed regularly. Users shall not have the ability to modify system time.

### 3.2 Preservation of Prior Entries

The system shall ensure that previously recorded audit trail entries cannot be overwritten, altered, or deleted by any user, including administrators. The original record shall remain visible alongside any subsequent modification. Backup copies of audit trail records shall be taken as part of the routine backup schedule defined in SYS-SOP-006.

### 3.3 Audit Trail Completeness

Audit trail configuration shall capture all GxP-relevant events across the system life cycle. Configuration gaps (e.g. events not captured) shall be treated as data integrity observations and addressed via the CAPA system.

## 4. Audit Trail Review

### 4.1 Frequency and Scope

Audit trails shall be reviewed at a frequency appropriate to the risk and activity of the system:

- High-frequency GxP systems (e.g. EBR, LIMS): reviewed within each batch record review cycle
- Lower-frequency systems (e.g. DMS, SCADA): reviewed at minimum quarterly

Audit trail review shall cover the period since the last review and shall be performed by a qualified reviewer independent of the data entry activity where practicable.

### 4.2 Review Criteria

The reviewer shall assess the audit trail for:

- Completeness: all expected events are captured
- Unexplained modifications: changes to GxP data without a documented reason
- Deleted records: records marked deleted shall be verified against authorised deletions
- Anomalous patterns: unusual timing, repeated failed actions, or access outside normal working hours

### 4.3 Documentation

The outcome of each audit trail review shall be recorded, including: system name, review period, reviewer identity, date of review, findings, and any actions raised. Review records shall be filed in the electronic batch record, the system's validation file, or the DMS as appropriate.

### 4.4 Handling Anomalies

Any unexplained or suspicious audit trail entry shall be escalated to QA immediately. A data integrity investigation shall be opened and completed before the associated batch record or data set is approved for release.

## 5. Regulatory Basis

This SOP implements 21 CFR Part 11 §11.10(e) (Audit trails for closed systems) and EudraLex Volume 4 Annex 11, Provision 9 (Audit Trails).
