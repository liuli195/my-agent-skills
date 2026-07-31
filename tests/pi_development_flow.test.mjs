import assert from "node:assert/strict";
import { access, mkdtemp, readFile, rm } from "node:fs/promises";
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
const pluginRoot = resolve(repoRoot, "plugins", "pi-development-flow");
const skillRoot = resolve(pluginRoot, "skills", "pi-development-flow");

const references = [
  "initialization.md",
  "requirements.md",
  "implementation.md",
  "delivery.md",
  "resume.md",
];

test("Pi discovers the local Development Flow package with disclosed references", async () => {
  const agentDir = await mkdtemp(join(tmpdir(), "pi-development-flow-"));
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
    const skill = result.skills.find(({ name }) => name === "pi-development-flow");
    assert.ok(skill, `missing pi-development-flow: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, pluginRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /development change/i);
    assert.match(formatSkillsForPrompt([skill]), /<name>pi-development-flow<\/name>/);

    const content = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");
    for (const name of references) {
      await access(resolve(skillRoot, "references", name));
      assert.match(content, new RegExp(`references/${name.replace(".", "\\.")}`));
    }
  } finally {
    await rm(agentDir, { recursive: true, force: true });
  }
});
