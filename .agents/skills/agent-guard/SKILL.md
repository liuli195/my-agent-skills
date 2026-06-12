---
name: agent-guard
description: Generate, activate, install, and maintain decoupled Agent Guard systems. Use when the user asks to guard a Skill, workflow, node, command, artifact lifecycle, Codex lifecycle behavior, PR review order, hook enforcement, dynamic guard injection, or a Guard Profile.
---

# agent-guard

Status: skeleton initialized. Do not treat scripts as implemented until their TODOs are replaced.

Use this skill to create and maintain decoupled Guard Runtime and Guard Profile systems.

Core rules:

- Investigate the guarded object before generating guard configuration.
- Do not modify the guarded Skill, workflow, or target object.
- Keep business rules in Guard Profile, not in hooks or Runtime.
- Require explicit user authorization before installing hooks.
- Require explicit user authorization before enabling blocking mode.
- Prefer Codex lifecycle hooks and Git hooks for MVP enforcement.

Read references as needed:

- `references/architecture.md` for the system split.
- `references/terminology.md` for canonical terms.
- `references/extraction-method.md` for interview and model extraction.
- `references/guard-profile.md` for Guard Profile layout.
- `references/runtime-contract.md` for Runtime behavior.
- `references/hook-contract.md` for hook binding rules.
- `references/subject-resolution.md` for Guard Instance matching.
- `references/guard-injection.md` for dynamic Guard Brief injection.
- `references/codex-claude-compat.md` for Codex and Claude compatibility.
