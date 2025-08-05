# 3. The CORE Governance Model

CORE's ability to evolve its own constitution is its most powerful and most dangerous capability. To ensure this process is safe, auditable, and aligned with human intent, it is governed by a strict, multi-stage **Constitutional Amendment Process**.

This process is designed to solve the central paradox of self-modification: **how can a system safely approve a change that might break its own ability to approve changes?**

## The Guiding Principle: The Canary Check

The entire process is built around a single, foolproof safety mechanism: the **"Canary" Check**.

Before any change is applied to the live constitution, the system performs a "what-if" simulation. It creates a temporary, isolated copy of itself in memory, applies the proposed change to this "canary," and then commands the canary to run a full self-audit.

-   If the canary, operating under the new proposed rules, reports a perfect, error-free audit, the change is deemed safe and is automatically applied to the live system.
-   If the canary's audit fails, it proves the change would create a broken or inconsistent state. The proposal is automatically rejected, and the live system is never touched.

This mechanism ensures that CORE can never approve an amendment that would render it unable to govern itself.

## The Life of a Constitutional Amendment

A change to any file within the `.intent/` directory follows a formal, five-step lifecycle.

### Step 1: Proposal (`.intent/proposals/`)

An AI agent or a human developer determines that a constitutional change is needed. They do not edit the target file directly. Instead, they create a formal **proposal file** in the `.intent/proposals/` directory.

This proposal is a YAML file containing:
-   `target_path`: The file to be changed.
-   `justification`: A human-readable reason for the change.
-   `content`: The full proposed new content of the file.

### Step 2: Signing (`core-admin proposals-sign`)

Constitutional changes require formal, cryptographic proof of human intent. A human operator uses the `core-admin` tool to sign the proposal with their private key.

```bash
# Generate a personal key pair (one-time setup)
core-admin keygen "your.name@example.com"

# Sign a pending proposal
core-admin proposals-sign cr-new-capability.yaml