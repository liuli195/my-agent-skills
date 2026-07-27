# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root.
- **`docs/comet/specs/`** — read specifications that touch the area you're about to work in.

If any of these files don't exist, **proceed silently**. Don't flag their absence or suggest creating them upfront. Create domain documentation only when terms or specifications actually get resolved.

## File structure

This repository uses a single-context layout:

```
/
├── CONTEXT.md
├── docs/comet/specs/
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, or a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, either reconsider whether you're inventing language the project doesn't use or note a real gap for `/domain-modeling`.

## Flag specification conflicts

If your output contradicts an existing specification, surface it explicitly rather than silently overriding it.
