---
name: pi-subagent-policy
description: Pi-only rules for subagent use. Use whenever the main agent decides to call any subagent; verify the persistent Explorer, Implementer, Reviewer, and Architect configurations, then select the role matching the delegated scenario.
---

# Pi Subagent Policy

The main agent decides whether and when to delegate.

## Check

Before the first delegation, check the effective persistent configuration once per session. Resolve project and global agent definitions using Pi Subagents precedence, confirm default agents are disabled, confirm each pinned model resolves in Pi's active model registry, and compare every enabled role's description, model, thinking level, capabilities, prompt mode, and prompt with this contract:

| Role | Description | Model | Thinking | Capabilities |
| --- | --- | --- | --- | --- |
| Explorer | Read-only investigator for delegated search, research, and evidence gathering. | `openai-codex/gpt-5.6-luna` | `low` | Read, search, read-only shell commands, and web search |
| Implementer | Implements delegated code or documentation from confirmed requirements. | `openai-codex/gpt-5.6-luna` | `max` | Full implementation tools; no extensions; preloaded TDD |
| Reviewer | Independently reviews delegated code or documentation against requirements and repository rules. | `openai-codex/gpt-5.6-sol` | `medium` | Read, search, and read-only shell commands |
| Architect | Read-only investigator for architecture, architectural decision-making, and difficult bug diagnosis. | `openai-codex/gpt-5.6-sol` | `max` | Read, search, and read-only shell commands |

Exactly these four roles are enabled. Every role uses `prompt_mode: append` and its matching prompt. Implementer additionally requires `extensions: false` and `skills: tdd` so non-isolated dispatch restores only the confirmed TDD skill.

- **Explorer:** Investigate the delegated question in read-only mode and return concise findings with evidence, source locations, and uncertainties.
- **Implementer:** Use `/skill:tdd` before implementing feature, bug, or integration behavior; follow the red-green loop, implement the delegated code or documentation task according to the provided requirements, repository rules, and existing patterns, verify the result, and report changes and unresolved issues.
- **Reviewer:** Independently review the delegated code or documentation scope against the provided requirements and repository rules; report actionable findings with severity and evidence.
- **Architect:** Investigate architecture, architectural decision-making, or difficult bug diagnosis in read-only mode.

If the effective configuration differs, report each difference and end this delegation. Configuration changes require user direction; persisted models and thinking levels remain authoritative.

## Route

Choose one role for the delegated work:

- **Explorer** for read-only search, investigation, and evidence gathering.
- **Implementer** for code or documentation changes from confirmed requirements.
- **Reviewer** for independent code or documentation review.
- **Architect** for architecture, architectural decision-making, or difficult bug diagnosis.

Work outside these roles stays with the main agent until the policy gains another role. The main agent writes the task prompt and chooses all unspecified runtime options.

## Accept

The main agent must verify a subagent result before relying on it or declaring the delegated work complete.
