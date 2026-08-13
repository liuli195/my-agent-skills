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
    const settingsManager = SettingsManager.inMemory({}, { projectTrusted: true });
    const loader = new DefaultResourceLoader({
      cwd: repoRoot,
      agentDir,
      settingsManager,
      additionalSkillPaths: [packageRoot],
      noExtensions: false,
      noSkills: true,
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
    });
    await loader.reload();

    const result = loader.getSkills();
    const skill = result.skills.find(({ name }) => name === "dev-flow");
    assert.ok(skill, `missing dev-flow: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "top-level");
    assert.equal(skill.sourceInfo.source, "local");
    assert.equal(skill.filePath, resolve(skillRoot, "SKILL.md"));
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
    const evidenceRoute = referenceContent[1].match(
      /## Evidence route[^]*?(?=\n## Completion)/i,
    )?.[0];
    const finalSmokeStep = evidenceRoute?.match(/\n4\.\s+[^]*?(?=\n5\.)/i)?.[0];
    assert.ok(finalSmokeStep, "missing Evidence route final smoke step");
    assert.match(
      finalSmokeStep,
      /Gate 1-bound target product entry[^]*primary success path[^]*risk-required failure or recovery paths[^]*confirmed by Gate 1/i,
    );
    assert.doesNotMatch(
      finalSmokeStep,
      /\bmain\b|\bdetached(?: state)?\b|unproven worktree|policy mismatch/i,
    );
    assert.match(content, /`subagent-policy`/);
    assert.match(content, /Gate 1 — Start Development（开始开发）/);
    assert.match(content, /Gate 2 — Specification and Delivery（规格与交付）/);
    assert.match(content, /Completion Check（完成检查）.*not.*third.*authorization/is);
    assert.match(content, /same Git worktree.*non-`main` feature branch/is);
    assert.match(content, /writable.*strictly serial|strictly serial.*writable/is);
    assert.doesNotMatch(devFlowText, /Implementer.*only writer|through the Implementer|Give the Implementer|new serial Implementer call/is);
    assert.match(content, /confirmation.*sticky.*recovery/is);
    assert.match(content, /### 核心摘要/);
    assert.match(content, /### 确认后进入的下一步/);
    assert.doesNotMatch(content, /Gate 3|Gate 4/);

    assert.match(
      referenceContent[0],
      /Gate 1[^]*target product[^]*highest real user entry[^]*observable success result[^]*failure or recovery paths/is,
    );
    assert.match(referenceContent[0], /Flow Level[^]*Fast[^]*Full/is);
    assert.match(
      referenceContent[0],
      /Fast[^]*(?:current session|current-session)[^]*(?:reproducible|replayable)[^]*(?:root cause|diagnosis)[^]*(?:public (?:test )?seam|highest real user entry)/is,
    );
    assert.match(referenceContent[0], /Full[^]*(?:default|otherwise)/is);
    assert.match(
      referenceContent[0],
      /(?:scope expands|scope expansion|second independent slice)[^]*(?:security|permission)|(?:security|permission)[^]*(?:scope expands|scope expansion|second independent slice)/is,
    );
    assert.match(referenceContent[0], /Gate 1[^]*Flow Level[^]*evidence/is);
    assert.match(
      referenceContent[1],
      /Red→Green[^]*final smoke[^]*behavior acceptance[^]*same entry/is,
    );
    assert.match(referenceContent[1], /independent review/i);
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
