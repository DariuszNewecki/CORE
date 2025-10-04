# Contributing to CORE

Thank you for joining CORE’s mission to pioneer self-governing software! Your contribution helps shape AI-driven development.

---

## Our Philosophy: Principled Contributions

CORE is governed by a **“constitution”** (rules in `.intent/`). All contributions must align with principles like `clarity_first`. Start with these docs:

*   **README.md**: Project vision and quick demo.
*   **Architecture (`docs/02_ARCHITECTURE.md`)**: The Mind-Body architecture and the role of the database.
*   **Governance (`docs/03_GOVERNANCE.md`)**: How changes are made safely.

**Key Concepts**:
*   A **`# ID: <uuid>`** tag in the source code is a permanent linker that connects a piece of code (the Body) to its definition in the database (the Mind).
*   A **"constitutional change"** updates files in `.intent/charter/`, requiring a signed proposal and a full audit.

---

## Contribution Workflow

1. **Find/Open an Issue**
   Discuss your proposed change in a GitHub Issue.

   ↓

2. **Write Your Code**
   Implement the feature or fix in `src/`.

   ↓

3. **Integrate Your Changes**
   Run `poetry run core-admin system integrate "Your commit message"` to tag, sync, and validate your work.

   ↓

4. **Submit a Pull Request**
   Link your PR to the issue.

---

## How to Contribute Code

Code contributions must follow CORE’s governance.

#### 1. Add Your Code
Write your functions, classes, and tests in the `src/` directory, following the established architectural domains.

#### 2. Assign IDs and Synchronize
After writing your code, you must integrate it with the system's Mind.

   *   **Assign IDs to new functions:**
     ```bash
     poetry run core-admin fix assign-ids --write
     ```
   *   **Synchronize with the database:**
     ```bash
     poetry run core-admin knowledge sync --write
     ```
   *   **(Optional) For major changes, run the full integration command:**
     ```bash
     poetry run core-admin system integrate "feat: Your descriptive commit message"
     ```

#### 3. Run Checks
Before submitting, ensure all checks pass. The `integrate` command does this for you, but you can also run them manually.

   *   `poetry run core-admin check ci audit`: Run the full constitutional audit (**required**).
   *   `make check`: A convenient shortcut for the full audit and other checks.
   *   `make format`: Auto-format your code.

#### 4. Submit Your PR
Submit your Pull Request, linking it to the relevant GitHub Issue.

---

## Questions?

Ask in **GitHub Issues**. We’re excited to collaborate!
