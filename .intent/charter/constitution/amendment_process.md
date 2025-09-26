# .intent/charter/constitution/amendment_process.md
#
# This document is the single, canonical source of truth for the process of
# amending the CORE Constitution. Adherence is mandatory for all changes to
# files governed by the Charter.

## SECTION 1: CORE PRINCIPLES OF AMENDMENT

1.  **Safety First:** The process is designed to prevent accidental or unauthorized changes. All critical changes require explicit, verifiable human approval.
2.  **Clarity and Intent:** Every proposed change must be accompanied by a clear justification that links it to the system's core principles or mission.
3.  **Auditability:** Every step of the amendment process, from proposal to ratification, must be traceable and recorded.

## SECTION 2: THE STANDARD AMENDMENT PROCESS

This process applies to any modification of a file within the `.intent/charter/` directory.

1.  **Proposal Creation:**
    *   An authorized operator MUST create a formal proposal file (`cr-*.yaml`) according to the `proposal_schema.json`.
    *   The `target_path` MUST be the canonical path to the Charter file being changed.
    *   The `justification` MUST clearly state the reason for the change and which CORE principle it serves.

2.  **Signature and Quorum:**
    *   The proposal MUST be signed by one or more authorized approvers as defined in `approvers.yaml`.
    *   The number of valid signatures MUST meet the quorum requirements defined in `approvers.yaml` for the current operational mode (`development` or `production`).
    *   For changes targeting files listed in `critical_paths.yaml`, the **critical** quorum is required. For all other Charter files, the **standard** quorum applies.

3.  **Validation and Ratification:**
    *   The proposed change MUST pass a full constitutional audit (`core-admin check ci audit`).
    *   The change MAY be subject to a canary deployment as defined in the `canary_policy.yaml`.
    *   Once all checks pass and the quorum is met, the change is considered ratified and can be merged.

## SECTION 3: EMERGENCY PROCEDURES

Emergency procedures, such as the revocation of a compromised key, are detailed in `charter/constitution/operator_lifecycle.md`. Such actions are considered critical amendments and always require the **critical** quorum.