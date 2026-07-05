# Access Control and Password Management SOP

**Document ID:** SYS-SOP-004
**Version:** 2.3
**Effective Date:** 2026-01-10
**Owner:** IT Security Lead
**Classification:** GxP Controlled Document

---

## 1. Purpose

This SOP defines the requirements for controlling access to GxP computerised systems and for managing the identification codes and passwords used to authenticate users of those systems at PharmaCo Ltd. It ensures that system access is restricted to authorised individuals and that credentials are managed in a manner that prevents unauthorised use.

## 2. Scope

This SOP applies to all GxP computerised systems and all personnel who access them, including employees, contractors, consultants, and vendor support personnel.

## 3. Access Provisioning

### 3.1 Authorisation

Access to a GxP system shall be granted only upon written approval from the system owner. The access request shall specify the role, the level of access required, and the business justification. Access shall not be provisioned until approval is confirmed and documented.

### 3.2 Role-Based Access Control

Access rights shall be assigned on a role basis reflecting the principle of least privilege. Users shall receive only the permissions required to perform their job function. Generic or shared accounts shall not be used in GxP systems.

### 3.3 Physical and Logical Access Controls

Where physical access to a system terminal is GxP-relevant, it shall be controlled (e.g. locked room, key card entry). Logical access controls shall require successful authentication before any system function is accessible.

The system shall record the identity of each operator and the date and time of all GxP data creation, modification, and review actions. Changes to access rights — granting, modifying, or revoking — shall be logged automatically by the system.

### 3.4 Third-Party and Remote Access

Vendor or third-party access shall be time-limited, monitored, and revoked immediately upon completion of the authorised activity. Remote access sessions shall be conducted via approved, secured channels only.

## 4. Identification Code and Password Controls

### 4.1 Uniqueness

Each user shall be assigned a unique identification code (user ID). User IDs shall never be reassigned to another individual. Retired user IDs shall not be reused.

### 4.2 Password Standards

Passwords shall meet the following minimum requirements:

- Minimum length: 12 characters
- Complexity: at least one uppercase letter, one lowercase letter, one numeral, and one special character
- Not contain the user's name, user ID, or common dictionary words

### 4.3 Periodic Revision

Passwords shall be changed at intervals not exceeding 90 days. Users shall be prompted by the system at the appropriate interval. Passwords shall not be reused within the previous 10 password cycles.

### 4.4 Lost or Compromised Credentials

If a user suspects their credentials have been compromised, they shall immediately notify the IT Help Desk and the system administrator. The compromised credentials shall be deauthorised within one business hour of notification. The incident shall be documented and assessed for potential impact on data integrity.

Accounts that have not been used for 60 consecutive calendar days shall be automatically suspended pending reactivation by the system owner.

### 4.5 Detection of Unauthorised Use

After five consecutive failed login attempts, the system shall automatically lock the account. The lockout shall be recorded in the system audit trail. Account reactivation shall require IT administrator intervention after identity verification.

Accounts shall be audited quarterly to confirm that access rights remain appropriate and that no inactive accounts are enabled.

## 5. Access Deprovisioning

User access shall be revoked within one business day of:

- Employment termination or role change
- Completion of a contractor engagement
- Completion of a vendor support activity

The deprovisioning action shall be documented and reviewed as part of the quarterly access audit.

## 6. Regulatory Basis

This SOP implements 21 CFR Part 11 §11.300 (Controls for identification codes/passwords) and EudraLex Volume 4 Annex 11, Provision 12 (Security).
