import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { formatSkillsForPrompt, loadSkillsFromDir } from "@earendil-works/pi-coding-agent";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = resolve(repoRoot, "plugins", "pi-subagent-policy");
const skillPath = resolve(pluginRoot, "skills", "pi-subagent-policy", "SKILL.md");

test("Pi discovers the model-invoked subagent policy", () => {
  const result = loadSkillsFromDir({ dir: pluginRoot, source: "test" });
  const skill = result.skills.find(({ name }) => name === "pi-subagent-policy");

  assert.ok(skill, `missing pi-subagent-policy: ${JSON.stringify(result.diagnostics)}`);
  assert.equal(skill.disableModelInvocation, false);
  assert.match(skill.description, /whenever the main agent decides to call any subagent/);
  assert.match(formatSkillsForPrompt([skill]), /<name>pi-subagent-policy<\/name>/);
});

test("the policy publishes the three persistent profiles", async () => {
  const content = await readFile(skillPath, "utf8");
  const expected = [
    "Explorer | `openai-codex/gpt-5.6-luna` | `low`",
    "Implementer | `openai-codex/gpt-5.6-terra` | `medium`",
    "Reviewer | `openai-codex/gpt-5.6-sol` | `medium`",
    "Investigate the delegated question in read-only mode and return concise findings with evidence, source locations, and uncertainties.",
    "Implement the delegated code or documentation task according to the provided requirements, repository rules, and existing patterns; verify the result and report changes and unresolved issues.",
    "Independently review the delegated code or documentation scope against the provided requirements and repository rules; report actionable findings with severity and evidence.",
    "check the effective persistent configuration once per session",
    "The main agent decides whether and when to delegate",
    "verify a subagent result before relying on it",
  ];

  for (const text of expected) assert.match(content, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});
