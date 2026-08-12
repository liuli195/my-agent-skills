import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
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
const packageRoot = resolve(repoRoot, "plugins", "subagent-policy");
const skillRoot = resolve(packageRoot, "skills", "subagent-policy");
const skillPath = resolve(skillRoot, "SKILL.md");

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const contract = [
  "The main agent decides whether and when to delegate.",
  "Check the effective host configuration once per session before the first delegation.",
  "exactly these four roles are enabled",
  "active model registry",
  "| Explorer | Read-only investigator for delegated search, research, and evidence gathering. | `openai-codex/gpt-5.6-luna` | `low` | Read, search, read-only shell commands, and web search |",
  "| Implementer | Implements delegated code or documentation from confirmed requirements. | `openai-codex/gpt-5.6-luna` | `max` | Full implementation tools; no extensions; preloaded TDD |",
  "| Reviewer | Independently reviews delegated code or documentation against requirements and repository rules. | `openai-codex/gpt-5.6-sol` | `medium` | Read, search, and read-only shell commands |",
  "| Architect | Read-only investigator for architecture, architectural decision-making, and difficult bug diagnosis. | `openai-codex/gpt-5.6-sol` | `max` | Read, search, and read-only shell commands |",
  "prompt_mode: append",
  "extensions: false",
  "skills: tdd",
  "Use `/skill:tdd` before implementing feature, bug, or integration behavior; follow the red-green loop",
  "Investigate the delegated question in read-only mode and return concise findings with evidence, source locations, and uncertainties.",
  "Independently review the delegated code or documentation scope against the provided requirements and repository rules; report actionable findings with severity and evidence.",
  "Investigate architecture, architectural decision-making, or difficult bug diagnosis in read-only mode.",
  "Only an exact match of every field permits selecting the corresponding host-native role.",
  "If any field differs, cannot be proven, or the host has no verified host Adapter（适配器）, stop before delegation.",
  "The main agent must verify the subagent's actual result before relying on it or declaring the work complete.",
];

test("Pi discovers the independent subagent-policy skill package and its fixed contract", async () => {
  const agentDir = await mkdtemp(join(tmpdir(), "subagent-policy-"));
  try {
    const settingsManager = SettingsManager.inMemory(
      { packages: [packageRoot] },
      { projectTrusted: true },
    );
    const loader = new DefaultResourceLoader({
      cwd: repoRoot,
      agentDir,
      settingsManager,
      noExtensions: false,
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
    });
    await loader.reload();

    const result = loader.getSkills();
    const skill = result.skills.find(({ name }) => name === "subagent-policy");
    assert.ok(skill, `missing subagent-policy: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, packageRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /before delegating any subagent/i);
    assert.match(formatSkillsForPrompt([skill]), /<name>subagent-policy<\/name>/);

    const packageExtensions = loader
      .getExtensions()
      .extensions.filter(({ resolvedPath }) => resolvedPath.startsWith(packageRoot));
    assert.deepEqual(packageExtensions, []);
    assert.deepEqual(await readdir(packageRoot), ["skills"]);
    assert.deepEqual(await readdir(resolve(packageRoot, "skills")), ["subagent-policy"]);
    assert.deepEqual(await readdir(skillRoot), ["SKILL.md"]);

    const content = await readFile(skillPath, "utf8");
    for (const text of contract) assert.match(content, new RegExp(escapeRegExp(text)));
    assert.match(content, /## Route[^]*host has no verified host Adapter（适配器）[^]*stop before delegation/is);
    assert.doesNotMatch(content, /\bClaude\b|\bCodex\b/);
  } finally {
    await rm(agentDir, { recursive: true, force: true });
  }
});
