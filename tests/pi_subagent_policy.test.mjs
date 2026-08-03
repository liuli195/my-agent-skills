import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  DefaultResourceLoader,
  formatSkillsForPrompt,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = resolve(repoRoot, "plugins", "pi-subagent-policy");
const skillPath = resolve(pluginRoot, "skills", "pi-subagent-policy", "SKILL.md");

test("Pi discovers the model-invoked policy through the local package entry", async () => {
  const agentDir = await mkdtemp(join(tmpdir(), "pi-subagent-policy-"));
  try {
    const settingsManager = SettingsManager.inMemory(
      { packages: [pluginRoot] },
      { projectTrusted: true },
    );
    const loader = new DefaultResourceLoader({
      cwd: repoRoot,
      agentDir,
      settingsManager,
      noExtensions: true,
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
    });
    await loader.reload();

    const result = loader.getSkills();
    const skill = result.skills.find(({ name }) => name === "pi-subagent-policy");
    assert.ok(skill, `missing pi-subagent-policy: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, pluginRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /whenever the main agent decides to call any subagent/);
    assert.match(formatSkillsForPrompt([skill]), /<name>pi-subagent-policy<\/name>/);
  } finally {
    await rm(agentDir, { recursive: true, force: true });
  }
});

test("the policy publishes the four persistent Subagent roles", async () => {
  const content = await readFile(skillPath, "utf8");
  const expected = [
    "Explorer | Read-only investigator",
    "Implementer | Implements delegated",
    "Reviewer | Independently reviews",
    "openai-codex/gpt-5.6-luna",
    "openai-codex/gpt-5.6-sol",
    "| Implementer | Implements delegated code or documentation from confirmed requirements. | `openai-codex/gpt-5.6-luna` | `max` | Full implementation tools; no extensions; preloaded TDD |",
    "extensions: false",
    "skills: tdd",
    "/skill:tdd",
    "check the effective persistent configuration once per session",
    "active model registry",
    "The main agent decides whether and when to delegate",
    "verify a subagent result before relying on it",
  ];

  for (const text of expected) assert.match(content, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});
