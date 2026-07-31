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

test("the policy publishes the three persistent Subagent roles", async () => {
  const content = await readFile(skillPath, "utf8");
  const expected = [
    "Explorer | Read-only investigator for delegated search, research, and evidence gathering. | `openai-codex/gpt-5.6-luna` | `low`",
    "Implementer | Implements delegated code or documentation from confirmed requirements. | `openai-codex/gpt-5.6-terra` | `medium`",
    "Reviewer | Independently reviews delegated code or documentation against requirements and repository rules. | `openai-codex/gpt-5.6-sol` | `medium`",
    "check the effective persistent configuration once per session",
    "The main agent decides whether and when to delegate",
    "verify a subagent result before relying on it",
  ];

  for (const text of expected) assert.match(content, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});
