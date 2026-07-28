# Design

## Root Cause

The Skill description says what `cross-agent-review` does, but not where it is allowed to run. That leaves room for generic review flows to invoke it after the Comet build gate has already handled the review evidence.

## Fix

Add a concise mandatory boundary section near the top of `SKILL.md`:

- ONLY ALLOWED: Comet build completion, PR Flow local review, or explicit user invocation.
- STRICTLY FORBIDDEN: Comet verify automatic invocation and generic code review automatic invocation.

The wording stays in the Skill document because this is an invocation policy for the Skill itself. The delta spec records that policy as the current `cross-agent-review` contract. Comet state logic, Agent Guard Runtime, and PR Flow code are not changed.

## Boundaries

- Do not change `cross_agent_review.py`.
- Do not change `review-pass.json` structure or output paths.
- Do not change Comet phase transitions.
- Do not add Comet-specific logic to Agent Guard Runtime.
- Do not remove PR Flow local review support.

## Verification

- Add a focused package test that asserts `SKILL.md` contains the mandatory boundary headings and core allowed/forbidden scenarios.
- Validate the OpenSpec delta.
- Run the focused cross-agent-review package test.
- Run the repository build check if the focused test passes.
