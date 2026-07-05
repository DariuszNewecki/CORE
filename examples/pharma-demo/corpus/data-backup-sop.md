# Data Backup and Storage Security SOP

**Document ID:** SYS-SOP-006
**Version:** 2.0
**Effective Date:** 2026-01-05
**Owner:** IT Infrastructure Manager
**Classification:** GxP Controlled Document

---

## 1. Purpose

This SOP defines the requirements for backup, storage, and protection of GxP electronic records at PharmaCo Ltd. It ensures that data is protected against physical damage, corruption, and loss through appropriate backup schedules and secure storage.

## 2. Scope

This SOP applies to all GxP-impacted computerised systems and the electronic records they contain, including batch records, laboratory data, validation documentation, and audit trail files.

## 3. Backup Schedule

### 3.1 Frequency

GxP system data shall be backed up according to the following schedule:

| System Class | Backup Frequency | Retention |
|---|---|---|
| Business-critical GxP (EBR, LIMS, MES) | Daily full + continuous incremental | 10 years |
| Secondary GxP (DMS, CDS) | Daily full | 5 years |
| Configuration data | Weekly full | 5 years |

Backup windows shall be scheduled to minimise impact on operational activities while ensuring that the maximum potential data loss (Recovery Point Objective) does not exceed 24 hours for critical systems and 48 hours for secondary systems.

### 3.2 Backup Media and Storage Location

Backup media shall be stored in a physically separate location from the primary data centre (minimum 10 km separation) to ensure protection against site-level events. Media shall be stored in an environment meeting the vendor's specifications for temperature, humidity, and protection against electromagnetic interference.

Backup media shall be clearly labelled with the system name, backup date, and media identifier. A media inventory shall be maintained and reconciled monthly.

### 3.3 Data Integrity of Backup Media

Backup jobs shall be monitored by the IT Operations team. Failed or incomplete backups shall be investigated and remediated within one business day. Monitoring alerts shall be reviewed daily by the on-call IT Operations engineer.

Backup media shall be protected against damage by physical and electronic means, including protection against fire, water, magnetic fields, and unauthorised access.

## 4. Data Accessibility

Electronic records shall remain accessible in a human-readable format throughout the required retention period. Where storage formats or media types become obsolete, data shall be migrated to current formats before the original media becomes unreadable. Migration activities shall be documented and validated.

Archived records shall be periodically sampled to confirm continued readability and accuracy. Sampling shall be conducted at least annually by the IT Compliance team.

## 5. Retention and Disposal

Electronic records shall be retained for the periods defined in the PharmaCo Records Retention Schedule (QMS-SOP-015), which complies with applicable regulatory requirements. At the end of the retention period, records shall be disposed of through a documented, secure disposal process. Disposal shall be recorded.

## 6. Regulatory Basis

This SOP supports data storage and protection requirements defined in EudraLex Volume 4 Annex 11, Provision 7 (Data Storage) and 21 CFR Part 11 §11.10 (Controls for closed systems).
