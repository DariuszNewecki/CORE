# Computer System Validation Policy

**Document ID:** SYS-POL-001
**Version:** 3.2
**Effective Date:** 2026-01-15
**Owner:** Head of IT Compliance
**Classification:** GxP Controlled Document

---

## 1. Purpose

This policy establishes the requirements for validation of computerised systems used in regulated GxP operations at PharmaCo Ltd. It defines the life-cycle approach for ensuring that systems are fit for their intended purpose and operate in a state of control throughout their operational life.

## 2. Scope

This policy applies to all computerised systems that impact product quality, data integrity, patient safety, or regulatory compliance, including:

- Laboratory Information Management Systems (LIMS)
- Electronic Batch Records (EBR) systems
- Manufacturing Execution Systems (MES)
- Document Management Systems (DMS)
- Chromatography data systems (CDS)

## 3. Validation Life-Cycle Requirements

### 3.1 Risk-Based Approach

All computer system validation activities shall be conducted using a risk-based approach. The extent of validation effort, testing depth, and documentation requirements shall be proportionate to the risk to product quality, patient safety, and data integrity.

A System Impact Assessment (SIA) and Computer System Risk Assessment (CSRA) shall be completed before validation planning begins, establishing whether a system is GxP-impacted and classifying it according to the GAMP 5 software category.

### 3.2 User Requirements Specification

Every system subject to validation shall have a documented User Requirements Specification (URS) prior to selection and qualification activities. The URS shall:

- State all functional and non-functional requirements traceable to business needs
- Identify GxP requirements and their regulatory basis
- Be approved by subject-matter experts, the system owner, and QA
- Serve as the primary reference for acceptance testing

### 3.3 Validation Testing

Validation testing shall demonstrate that the system meets all URS requirements across its intended operating ranges. Testing evidence shall include:

- Installation Qualification (IQ): confirming correct installation against vendor specifications
- Operational Qualification (OQ): verifying that the system operates as specified across its intended range
- Performance Qualification (PQ): demonstrating sustained performance under representative production conditions

All test protocols shall be pre-approved before execution. Deviations encountered during testing shall be documented, investigated, and resolved before a system is released for GxP use.

### 3.4 Audit Trail Configuration

Systems shall be configured to capture complete, system-generated audit trails for all GxP-relevant data creation, modification, or deletion events. Audit trail configuration shall be verified as part of IQ/OQ. The system's audit trail capability shall not be disabled or bypassed after validation.

### 3.5 Validation Documentation

The validation life-cycle documentation shall include as a minimum: URS, Validation Plan, Risk Assessment, IQ/OQ/PQ protocols and reports, Validation Summary Report, and System Release Authorisation. All documents shall be stored in the PharmaCo document management system under controlled access.

## 4. Change Control

Any change to a validated system — hardware, software, configuration, or operating environment — shall be assessed for potential impact on the validated state. Changes requiring re-validation shall be documented via Change Control and appropriate re-qualification executed before the changed system is returned to GxP use.

## 5. Periodic Review

Validated systems shall be reviewed at defined intervals (minimum annually) to confirm they remain in a validated, GxP-compliant state. Periodic review shall assess: system performance, open deviations, change history, vendor support status, and user access rights.

## 6. Roles and Responsibilities

| Role | Responsibility |
|------|----------------|
| System Owner | Defines requirements; authorises system for GxP use |
| IT Compliance | Executes and coordinates validation activities |
| Quality Assurance | Reviews and approves all validation documentation |
| Users | Execute testing; report deviations |

## 7. Regulatory Basis

This policy is aligned with EudraLex Volume 4 Annex 11 (Computerised Systems), 21 CFR Part 11 (Electronic Records; Electronic Signatures), and the GAMP 5 guide. In the event of conflict between this policy and applicable regulations, the regulation takes precedence.
