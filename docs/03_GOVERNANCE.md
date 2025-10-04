03_GOVERNANCE.md
The CORE Governance Model
For New Users: How CORE Makes Changes Safely
CORE evolves like a government with checks and balances. To change a rule (a file in .intent/), you must:
Propose the change in writing.
Sign it with a cryptographic key to prove human intent.
Have enough approvers sign it (a "quorum").
Let CORE test the change in a safe sandbox (Canary Check).
This process prevents accidental or unauthorized changes to the system's constitution.
👉 Try It: Generate your personal cryptographic key with one command:
code
Bash
poetry run core-admin keys keygen "your.email@example.com"
The Guiding Principle: The Canary Check
Before any constitutional change is applied, CORE runs a "canary check". It creates a temporary, in-memory copy of the entire system, applies the proposed change to it, and runs a full self-audit.
✅ If the audit passes, the change is applied to the live system.
❌ If the audit fails, the change is automatically rejected, and the live system is never touched.
This ensures that a faulty constitutional amendment can never break the system.
The Life of a Constitutional Amendment
Updating .intent/ is a formal, 5-step process orchestrated by the core-admin proposals command group.
code
Mermaid
graph TD
    A[1. Draft Proposal] --> B[2. Sign Proposal]
    B --> C[3. Verify Quorum]
    C --> D[4. Run Canary Audit]
    D --> E[5. Ratify & Apply]
Step 1: Draft the Proposal
Create a YAML file in the .intent/proposals/ directory (e.g., cr-new-rule.yaml). This file must state what you want to change (target_path) and why (justification).
Step 2: Sign the Proposal
Use the core-admin CLI to cryptographically sign the proposal with your private key.
code
Bash
poetry run core-admin proposals sign cr-new-rule.yaml
Step 3: Verify Quorum
The system checks .intent/constitution/approvers.yaml to see if enough authorized operators have signed the proposal.
Standard changes (e.g., updating a policy) typically require 1 signature.
Critical changes (e.g., adding a new approver) require more.
Step 4: Approve and Run Canary Check
A maintainer runs the approve command. This triggers the signature verification and the critical canary check.
code
Bash
poetry run core-admin proposals approve cr-new-rule.yaml
Output:
code
Text
✅ Canary audit PASSED. Change is constitutionally valid.
✅ Successfully approved and applied 'cr-new-rule.yaml'.
Step 5: Ratification
If the canary audit passes, the change is applied to the target file, and the proposal is archived. The system's constitution has now evolved safely.
Takeaways
CORE's evolution is governed by a safe, auditable, and cryptographically secure process.
The canary check is the ultimate safety net that prevents self-inflicted damage.
Next: See the Project Roadmap to understand where the project is evolving next.
