FILE: docs/09_WORKED_EXAMPLE.md
Worked Example: Your First Governed Application
⏱️ Time: ~5 minutes

For New Users: See CORE in Action
This demo creates a "Quote of the Day" API, intentionally breaks a rule, and shows CORE's auditor catching the violation. No experience needed — just follow the commands!

Step 1: Create a New Application
From the root of the CORE project, run the following command. This uses a built-in starter kit to scaffold a new, governed application in the work/ directory.
bashpoetry run core-admin new quote-api --write
Output:
text✅ Successfully scaffolded 'quote-api' in 'work/'.
What Happens: CORE builds a new project at work/quote-api/ complete with its own constitution (.intent/) and basic source code (src/).

Step 2: See the Generated "Mind"
Check the architectural rules for your new application. This file acts as a blueprint for your code, enforced by the auditor.
File: work/quote-api/.intent/knowledge/source_structure.yaml
yamlstructure:
  - domain: main
    path: src/main
    description: "The primary domain for this application's core logic."
    allowed_imports: [main, shared]
  - domain: shared
    path: src/shared
    description: "Shared utilities and data models."
    allowed_imports: [shared]
Meaning: Code in the main domain is only allowed to import modules from shared or from within main itself. This prevents spaghetti code.

Step 3: Intentionally Violate the Constitution
Now, let's break that rule. Edit the main API file to add a forbidden import and some logic that doesn't belong there (direct file I/O).
Edit work/quote-api/src/main/api.py and add the following:
python# work/quote-api/src/main/api.py
import os  # ❌ Forbidden import!

def log_quote_to_disk(quote: str):
    """Log a quote to disk."""
    with open("/tmp/quotes.log", "a") as f:
        f.write(quote + "\n")
Why is this wrong?

Illegal Import: The main domain is not allowed to import os.
Misplaced Responsibility: Direct file I/O is a side effect that should be handled in a dedicated services or shared domain, not in the main API logic.


Step 4: Run the Constitutional Audit
Now, ask CORE to audit your new application. The system audit command acts as an AI architect, checking the code against the constitutional rules.
bash# Run the audit from within your new project's directory
cd work/quote-api
poetry run core-admin system audit
Expected Output:
You will see the auditor fail with a clear error message:
text[ERROR] 🚨 Domain Violation in src/main/api.py:
        Forbidden import of 'os'. The 'main' domain is only allowed to import from: ['main', 'shared'].
        This violates the 'separation_of_concerns' principle.

The Value Proposition
You've just seen CORE do something a normal linter can't: it caught an architectural violation.
By declaring your intent for how the system should be structured, you've empowered an AI partner to help you maintain that structure as the codebase evolves. This prevents architectural drift and keeps your project clean and maintainable over the long term.

Next Steps
Now that you've seen the auditor in action, try running the self-healing commands to fix other issues:

poetry run core-admin fix docstrings --write
poetry run core-admin system format

Explore the other documentation to learn more about CORE's capabilities.
