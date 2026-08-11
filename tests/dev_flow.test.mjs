import assert from "node:assert/strict";
import { access, mkdtemp, readFile, readdir, rm } from "node:fs/promises";
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
const packageRoot = resolve(repoRoot, "plugins", "dev-flow");
const skillRoot = resolve(packageRoot, "skills", "dev-flow");
const references = ["requirements.md", "implementation.md", "delivery.md"];

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

test("Pi discovers the pure Development Flow package and its disclosed stage references", async () => {
  const agentDir = await mkdtemp(join(tmpdir(), "dev-flow-"));
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
    const skill = result.skills.find(({ name }) => name === "dev-flow");
    assert.ok(skill, `missing dev-flow: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, packageRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /same Git worktree|single worktree/i);
    assert.match(skill.description, /non-main|feature branch/i);
    assert.match(formatSkillsForPrompt([skill]), /<name>dev-flow<\/name>/);

    const packageExtensions = loader
      .getExtensions()
      .extensions.filter(({ resolvedPath }) => resolvedPath.startsWith(packageRoot));
    assert.deepEqual(packageExtensions, []);
    assert.deepEqual(await readdir(packageRoot), ["skills"]);
    assert.deepEqual(await readdir(resolve(packageRoot, "skills")), ["dev-flow"]);
    assert.deepEqual(
      (await readdir(skillRoot)).sort(),
      ["SKILL.md", "references"].sort(),
    );
    assert.deepEqual(
      (await readdir(resolve(skillRoot, "references"))).sort(),
      [...references].sort(),
    );

    const content = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");
    const referenceContent = await Promise.all(
      references.map((name) => readFile(resolve(skillRoot, "references", name), "utf8")),
    );
    const devFlowText = [content, ...referenceContent].join("\n");
    assert.match(content, /`subagent-policy`/);
    assert.match(content, /Gate 1 — Start Development（开始开发）/);
    assert.match(content, /Gate 2 — Specification and Delivery（规格与交付）/);
    assert.match(content, /Completion Check（完成检查）.*not.*third.*authorization/is);
    assert.match(content, /same Git worktree.*non-`main` feature branch/is);
    assert.match(content, /Implementer.*only writer.*serial/is);
    assert.match(content, /confirmation.*sticky.*recovery/is);
    assert.match(content, /### 核心摘要/);
    assert.match(content, /### 确认后进入的下一步/);
    assert.doesNotMatch(content, /Gate 3|Gate 4/);

    assert.match(
      referenceContent[0],
      /Gate 1[^]*target product[^]*highest real user entry[^]*observable success result[^]*failure or recovery paths/is,
    );
    assert.match(
      referenceContent[1],
      /Red→Green[^]*final smoke[^]*behavior acceptance[^]*same entry/is,
    );
    assert.doesNotMatch(devFlowText, /real Pi entry smoke/i);
    assert.doesNotMatch(devFlowText, /Claude and Codex/i);
    assert.doesNotMatch(devFlowText, /\b(?:Pi|Claude|Codex)\b/i);

    for (const name of references) {
      await access(resolve(skillRoot, "references", name));
      assert.match(content, new RegExp(`references/${escapeRegExp(name)}`));
    }
  } finally {
    await rm(agentDir, { recursive: true, force: true });
  }
});
