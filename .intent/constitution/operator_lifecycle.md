# Human Operator Lifecycle Procedures

This document defines the formal, constitutionally-mandated procedures for managing human operators who have the authority to approve changes to the CORE constitution. Adherence to these procedures is mandatory and enforced by peer review during any change to the `approvers.yaml` file.

## Onboarding a New Approver

1.  **Key Generation:** The candidate operator MUST generate a new, secure Ed25519 key pair using the following command from the CORE repository root:
    ```bash
    poetry run core-admin keygen "candidate.email@example.com"
    ```
2.  **Proposal Creation:** A currently active, authorized approver MUST create a formal constitutional amendment proposal.
    - The `target_path` of the proposal MUST be `.intent/constitution/approvers.yaml`.
    - The `justification` MUST clearly state the reason for adding the new approver, including their role and identity.
    - The `content` of the proposal MUST be the complete `approvers.yaml` file with the new approver's YAML block appended.
3.  **Ratification:** The proposal must be signed and approved, meeting the required quorum as defined in `approvers.yaml`. Upon successful canary validation and approval, the new operator is considered active.

## Standard Revocation of an Approver

1.  **Proposal Creation:** An authorized approver MUST create a formal proposal to remove the target operator's block from the `approvers` list in `approvers.yaml`.
2.  **Justification:** The `justification` MUST clearly state the non-emergency reason for revocation (e.g., operator has left the project).
3.  **Ratification:** The proposal must be signed and approved, meeting the required quorum.

## Emergency Revocation of a Compromised Key

1.  **Proposal Creation:** In the event of a suspected or confirmed private key compromise, any active approver MUST immediately create an emergency revocation proposal targeting `approvers.yaml`.
2.  **Quorum:** This proposal requires the **critical** quorum to be met for approval.
3.  **Immediate Invalidation:** The moment a revocation proposal is created for an identity, that identity's signature is considered invalid for all quorum calculations on that proposal and any subsequent proposals until the matter is resolved.