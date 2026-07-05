# Electronic Records and Data Integrity SOP

**Document ID:** SYS-SOP-002
**Version:** 2.1
**Effective Date:** 2026-02-01
**Owner:** IT Compliance Manager
**Classification:** GxP Controlled Document

---

## 1. Purpose

This SOP defines the controls required for the creation, modification, review, and retention of electronic records in GxP environments at PharmaCo Ltd. It ensures that electronic records are authentic, accurate, complete, and protected against loss or unauthorised modification in closed computerised systems.

## 2. Scope

This SOP applies to all GxP electronic records created, processed, or stored in closed computerised systems. A closed system is one where system access is controlled by the same organisation that is responsible for the content of the electronic records.

## 3. Closed System Controls

### 3.1 System Validation

All closed systems holding GxP electronic records shall be validated in accordance with SYS-POL-001 (Computer System Validation Policy) prior to use for GxP purposes. System validation provides the documented evidence that the system will consistently produce records that are accurate, reliable, and complete.

### 3.2 Access and Authority Checks

Access to systems containing GxP electronic records shall be restricted to authorised personnel. Access rights shall be role-based and reflect the principle of least privilege. The system shall enforce operational checks to determine the validity of the source of data input at the time of data entry.

Where operational checks are not technically feasible, compensating controls (e.g. second-person review procedures) shall be documented and implemented.

### 3.3 Data Checks on Entry and Exchange

Computerised systems shall include built-in checks for the correct and secure entry and processing of data. For systems that exchange data electronically with other systems, the following controls shall be in place:

- Automated validation of data format and range at point of entry
- Checksums or equivalent integrity verification for data transmitted between systems
- Error alerts and rejection mechanisms for data that fails validation criteria
- Reconciliation procedures to confirm completeness and accuracy of data transfer

These controls shall be verified as part of system qualification and any subsequent configuration change.

### 3.4 Audit Trails

All GxP-critical systems shall maintain system-generated, computer time-stamped audit trails that independently record the date and time of operator entries and actions that create, modify, or delete electronic records. Audit trail entries shall not be modifiable or deletable by any user, including system administrators.

Audit trail records shall be retained for the same period as the associated electronic record and shall be available for review during regulatory inspections.

### 3.5 Record Integrity During Retention

Electronic records shall be protected from deterioration and loss throughout their required retention period through:

- Routine backup procedures as defined in SYS-SOP-005 (Data Backup and Recovery SOP)
- Periodic checks confirming readability, accessibility, and accuracy of backed-up records
- Migration procedures when storage technology approaches obsolescence

## 4. Record Review Requirements

Personnel reviewing electronic records shall have appropriate system access and receive training in electronic data review expectations. Reviews shall confirm that records are complete, accurate, and created in the normal course of operations without data manipulation.

## 5. Regulatory Basis

This SOP implements requirements of 21 CFR Part 11 Subpart B (Electronic Records, §11.10) and EudraLex Volume 4 Annex 11, Provision 5 (Data) and Provision 9 (Audit Trails).
