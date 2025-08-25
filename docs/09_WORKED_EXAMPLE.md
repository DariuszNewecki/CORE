# Worked Example: Your First Governed Application

⏱️ **Time: \~5 minutes**

---

## For New Users: See CORE in Action

This demo creates a **“Quote of the Day” API**, breaks a rule, and shows CORE fixing it.
No experience needed — just follow the commands!

---

## Step 1: Create a New Application

From CORE root:

```bash
poetry run core-admin new quote-api --profile default
# Output: Created work/quote-api/
```

**What Happens:** Builds `work/quote-api/` with `.intent/` (rules) and `src/` (code).

---

## Step 2: See the Generated "Mind"

Check `work/quote-api/.intent/source_structure.yaml`:

```yaml
structure:
  - domain: main
    path: src/main
    allowed_imports: [shared]
```

**Meaning:** `main` domain can only import `shared`.

---

## Step 3: Intentionally Violate the Constitution

Edit `work/quote-api/src/main/api.py`:

```python
# src/main/api.py
import os  # ❌ Forbidden import!

def log_quote_to_disk(quote: str):
    """Log a quote to disk."""
    with open("/tmp/quotes.log", "a") as f:
        f.write(quote + "\n")
```

**Why Wrong?** File I/O belongs in a **services domain**.

💡 *Screenshot Note*: Visualize this in your editor — `api.py` now has an error.

---

## Step 4: Run the Constitutional Audit

```bash
poetry run core-admin byor-init work/quote-api
```

**Output:**

```
[ERROR] 🚨 Domain Violation
File: src/main/api.py
Problem: Imported 'os' (not in allowed_imports)
Rule: 'main' only imports 'shared'
```

---

## The Value Proposition

CORE catches **architectural mistakes early**, unlike linters.

**For experts:** Integrate with CI via `make audit`.

---

## Troubleshooting

* **Command fails?** Use `poetry shell` or check `.env` for keys.
* **No errors?** Verify `reports/drift_report.json`.

---

## Takeaways

* Automated **governance saves time**.
* **Next**: Try **BYOR** on your project.

---

## Contribute

Add a **test for this scenario**! See `CONTRIBUTING.md`.
