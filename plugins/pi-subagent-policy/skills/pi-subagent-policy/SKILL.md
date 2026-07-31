---
name: pi-subagent-policy
description: Pi-only rules for subagent use. Use whenever the main agent decides to call any subagent; verify the persistent Explorer, Implementer, and Reviewer configurations, then select the role matching the delegated scenario.
---

# Pi Subagent Policy

The main agent decides whether and when to delegate.

## Check

Before the first delegation, check the effective persistent configuration once per session. Resolve project and global agent definitions using Pi Subagents precedence, confirm default agents are disabled, and confirm that exactly these three enabled roles and models are available:

| Role | Model | Thinking | Capabilities |
| --- | --- | --- | --- |
| Explorer | `openai-codex/gpt-5.6-luna` | `low` | Read, search, read-only shell commands, and web search |
| Implementer | `openai-codex/gpt-5.6-terra` | `medium` | Full implementation tools |
| Reviewer | `openai-codex/gpt-5.6-sol` | `medium` | Read, search, and read-only shell commands |

Every role uses `prompt_mode: append` and its matching prompt:

- **Explorer:** Investigate the delegated question in read-only mode and return concise findings with evidence, source locations, and uncertainties.
- **Implementer:** Implement the delegated code or documentation task according to the provided requirements, repository rules, and existing patterns; verify the result and report changes and unresolved issues.
- **Reviewer:** Independently review the delegated code or documentation scope against the provided requirements and repository rules; report actionable findings with severity and evidence.

If the effective configuration differs, report each difference and end this delegation. Configuration changes require user direction; persisted models and thinking levels remain authoritative.

## Route

Choose one role for the delegated work:

- **Explorer** for read-only search, investigation, and evidence gathering.
- **Implementer** for code or documentation changes from confirmed requirements.
- **Reviewer** for independent code or documentation review.

Work outside these roles stays with the main agent until the policy gains another role. The main agent writes the task prompt and chooses all unspecified runtime options.

## Accept

The main agent must verify a subagent result before relying on it or declaring the delegated work complete.
