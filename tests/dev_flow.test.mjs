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
  const originalHome = process.env.HOME;
  const originalUserProfile = process.env.USERPROFILE;
  process.env.HOME = agentDir;
  process.env.USERPROFILE = agentDir;
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
    assert.match(skill.description, /同一个 Git（版本管理）工作树/);
    assert.match(skill.description, /非 main（主干）功能分支/);
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
    for (const [name, text] of [
      ["SKILL.md", content],
      ...references.map((name, index) => [name, referenceContent[index]]),
    ]) {
      const headings = [...text.matchAll(/^## (.+)$/gm)].map((match) => match[1]);
      assert.deepEqual(
        headings,
        ["MUST — 必须依赖", "流程编排"],
        `${name} 必须且只能依次包含两个顶层编排模块`,
      );
    }
    assert.match(referenceContent[0], /当前会话[^]*`grill-with-docs`[^]*`domain-modeling`[^]*`to-spec`[^]*`to-tickets`/);
    assert.match(referenceContent[0], /当前门禁[^]*明确授权/);
    assert.match(referenceContent[0], /不得要求固定回复措辞/);
    assert.match(referenceContent[0], /沉默[^]*提问[^]*修改需求[^]*不能视为授权/);
    assert.doesNotMatch(devFlowText, /只请求`开始开发`|只请求`规格与交付`|回复[^]*等于[^]*`开始开发`/);
    const implementationSteps = referenceContent[1].match(
      /## 流程编排[^]*$/,
    )?.[0];
    const finalSmokeStep = implementationSteps?.match(/\n5\.\s+[^]*?(?=\n6\.)/)?.[0];
    assert.ok(finalSmokeStep, "缺少流程编排中的最终冒烟步骤");
    assert.match(
      finalSmokeStep,
      /门禁一绑定的目标产品入口[^]*主要成功路径[^]*门禁一确认的风险所要求的失败或恢复路径/,
    );
    assert.doesNotMatch(
      finalSmokeStep,
      /`main`|detached HEAD（分离头）|无法证明工作树|策略不匹配/,
    );
    assert.match(content, /`subagent-policy`/);
    assert.match(content, /门禁一——开始开发/);
    assert.match(content, /门禁二——规格与交付/);
    assert.match(content, /完成检查不是第三个授权门禁/);
    assert.match(content, /同一工作树和分支/);
    assert.match(content, /可写调用必须严格串行/);
    assert.doesNotMatch(devFlowText, /Implementer（实施者）是唯一写入者|通过 Implementer（实施者）|交给 Implementer（实施者）|新的串行 Implementer（实施者）调用/);
    assert.match(content, /确认在已确认动作及其失败恢复期间持续有效/);
    assert.match(content, /### 核心摘要/);
    assert.match(content, /### 确认后进入的下一步/);
    assert.doesNotMatch(content, /Gate 3|Gate 4/);

    assert.match(
      referenceContent[0],
      /门禁一[^]*目标产品[^]*最高层级真实用户入口[^]*可观察成功结果[^]*失败或恢复路径/,
    );
    assert.match(referenceContent[0], /流程等级[^]*Fast（快速）[^]*Full（完整）/);
    assert.match(
      referenceContent[0],
      /Fast（快速）[^]*当前会话[^]*可复现[^]*根因[^]*(?:公开测试接缝|最高层级真实用户入口)/,
    );
    assert.match(referenceContent[0], /Full（完整）\*\*是其他情况的默认等级/);
    assert.match(
      referenceContent[0],
      /(?:范围扩大|第二个独立切片)[^]*(?:安全|权限)|(?:安全|权限)[^]*(?:范围扩大|第二个独立切片)/,
    );
    assert.match(referenceContent[0], /门禁一[^]*流程等级[^]*证据/);
    assert.match(
      referenceContent[1],
      /红灯到绿灯检查、最终冒烟和行为验收均使用同一入口/,
    );
    assert.match(referenceContent[1], /独立审查/);
    assert.doesNotMatch(devFlowText, /real Pi entry smoke/i);
    assert.doesNotMatch(devFlowText, /Claude and Codex/i);
    assert.doesNotMatch(devFlowText, /\b(?:Pi|Claude|Codex)\b/i);

    for (const name of references) {
      await access(resolve(skillRoot, "references", name));
      assert.match(content, new RegExp(`references/${escapeRegExp(name)}`));
    }
  } finally {
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
    if (originalUserProfile === undefined) delete process.env.USERPROFILE;
    else process.env.USERPROFILE = originalUserProfile;
    await rm(agentDir, { recursive: true, force: true });
  }
});
