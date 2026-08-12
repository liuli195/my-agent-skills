---
name: subagent-policy
description: Host-neutral rules for validating fixed subagent role contracts before delegating any subagent; use when the main agent is about to delegate work.
---

# Subagent Policy（子代理策略）

This Skill（技能） defines the host-neutral contract for selecting a named Subagent role（子代理角色）. The main agent decides whether and when to delegate. This Skill does not decide whether delegation is useful, install configuration, or implement a runtime dispatcher.

## Check（校验）

Check the effective host configuration once per session before the first delegation. Prove all of the following before selecting a role:

1. Confirm default agents are disabled; exactly these four roles are enabled, with no unregistered roles.
2. Every enabled role's description, model, thinking level, capabilities/resources, `prompt_mode`, and prompt exactly match this contract.
3. Confirm each pinned model resolves in the host's active model registry (Pi's active model registry for the Pi mapping).
4. The host has a verified native mapping for this contract. This package provides only the Pi mapping below.

A missing value, an unprovable value, a project override, a model-resolution failure, or any other difference is a failed check. Do not repair, override, inherit, downgrade, or retry with another role.

## Fixed role contract（固定角色契约）

| Role | Description | Pi model | Thinking | Capabilities/resources |
| --- | --- | --- | --- | --- |
| Explorer | Read-only investigator for delegated search, research, and evidence gathering. | `openai-codex/gpt-5.6-luna` | `low` | Read, search, read-only shell commands, and web search |
| Implementer | Implements delegated code or documentation from confirmed requirements. | `openai-codex/gpt-5.6-luna` | `max` | Full implementation tools; no extensions; preloaded TDD |
| Reviewer | Independently reviews delegated code or documentation against requirements and repository rules. | `openai-codex/gpt-5.6-sol` | `medium` | Read, search, and read-only shell commands |
| Architect | Read-only investigator for architecture, architectural decision-making, and difficult bug diagnosis. | `openai-codex/gpt-5.6-sol` | `max` | Read, search, and read-only shell commands |

Every role uses `prompt_mode: append` and its matching prompt:

- **Explorer:** Investigate the delegated question in read-only mode and return concise findings with evidence, source locations, and uncertainties.
- **Implementer:** Use `/skill:tdd` before implementing feature, bug, or integration behavior; follow the red-green loop, implement the delegated code or documentation task according to the provided requirements, repository rules, and existing patterns, verify the result, and report changes and unresolved issues.
- **Reviewer:** Independently review the delegated code or documentation scope against the provided requirements and repository rules; report actionable findings with severity and evidence.
- **Architect:** Investigate architecture, architectural decision-making, or difficult bug diagnosis in read-only mode.

For the Pi Implementer mapping, also prove `extensions: false` and `skills: tdd`. These are host resource settings, not resources provided by this package.

## Route（路由）

Only an exact match of every field permits selecting the corresponding host-native role. When the check passes, select that role without temporary model, thinking, capability, or prompt overrides.

If any field differs, cannot be proven, or the host has no verified host Adapter（适配器）, stop before delegation. Do not silently select a default, generic, unregistered, or fallback role.

## Accept（验收）

A returned report is not proof of completion. The main agent must verify the subagent's actual result before relying on it or declaring the work complete. Verify the observed host result and the task-specific evidence, such as the actual role and runtime metadata, files, branch, diff, and checks, before accepting the result.
