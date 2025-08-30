# 6. Starter Kits & The Philosophy of Intent

## The CORE Partnership

CORE is not a vending machine for code. It is an intelligent partner designed to translate a human's intent into a governed, working software system. This partnership requires two things:

1. **The Human's Responsibility:** Provide a clear, high-level intent—the "why" behind the project.
2. **CORE's Responsibility:** Translate that intent into a complete system, asking for clarification and guidance along the way.

If the human provides no intent ("I do not care"), CORE will do nothing. The partnership requires a starting point.

---

## Starter Kits: Your First Declaration of Intent

To facilitate this partnership, the `core-admin new` command uses **Starter Kits**. A starter kit is not just a collection of template files; it is a **pre-packaged declaration of intent**. It is a way for you to tell CORE about the *kind* of system you want to build from day one.

By choosing a starter kit, you are providing the "minimal viable intent" that CORE needs to begin its work.

---

### How to Use Starter Kits

When you create a new project, you can specify a `--profile` option. This tells the scaffolder which starter kit to use.

```bash
# Scaffold a new project using the 'default' balanced starter kit
poetry run core-admin new my-new-app --profile default

# Scaffold a project with high-security policies from the start
poetry run core-admin new my-secure-api --profile security
```

If you do not provide a profile, CORE will default to the safest, most balanced option.

---

## The Life of a Starter Kit

* **Scaffolding:** CORE creates your new project structure and populates the `.intent/` directory with the constitutional files from your chosen starter kit.
* **Ownership:** From that moment on, that constitution is yours. It is no longer a template. It is the living *Mind* of your new project.
* **Evolution:** You can (and should) immediately begin to amend and evolve your new constitution to perfectly match your project's unique goals, using the standard proposals workflow.

Starter kits are just the beginning of the conversation, not the end. They are the most effective way to kickstart the CORE partnership and begin the journey of building a truly intent-driven system.
