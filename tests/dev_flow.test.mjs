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
const changeName = "2026-08-14-enforce-dev-flow-dependency-artifacts";

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function assertInOrder(text, ...needles) {
  let offset = -1;
  for (const needle of needles) {
    const next = text.indexOf(needle, offset + 1);
    assert.ok(next > offset, `expected ${needle} after ${needles[needles.indexOf(needle) - 1] ?? "the start"}`);
    offset = next;
  }
}

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
    assert.match(referenceContent[0], /完整展示当前门禁[^]*用户[^]*明确授权[^]*当前门禁动作/);
    assert.doesNotMatch(
      devFlowText,
      /固定口令|固定回复措辞|逐字回复|不能视为授权|不得要求用户|“确认”“可以”“继续实施\/交付”/,
    );
    assert.doesNotMatch(content, /^### /m, "入口应保持薄路由，不展开阶段细节");
    assert.doesNotMatch(content, /Red→Green|status: passed|checked|removeWorktreePending/);

    const phaseDependencies = {
      "requirements.md": [
        "subagent-policy",
        "codebase-design",
        "grill-with-docs",
        "grilling",
        "domain-modeling",
        "to-spec",
        "to-tickets",
      ],
      "implementation.md": [
        "subagent-policy",
        "tdd",
        "build-and-verify",
        "code-review",
      ],
      "delivery.md": [
        "my-spec",
        "my-spec-add",
        "pr-flow-complete",
        "resolving-merge-conflicts",
      ],
    };
    for (const [name, dependencies] of Object.entries(phaseDependencies)) {
      const text = referenceContent[references.indexOf(name)];
      for (const dependency of dependencies) {
        assert.match(text, new RegExp("`" + escapeRegExp(dependency) + "`"));
      }
      assert.match(text, /## MUST — 必须依赖/);
      assert.match(text, /## 流程编排/);
    }

    assert.match(content, /宿主[^]*技能清单[^]*精确技能名[^]*唯一[^]*location/);
    assert.match(content, /`~\/\.agents\/skills\/<skill-name>\/SKILL\.md`/);
    assert.match(content, /本入口 `dev-flow` SKILL\.md 中的阶段参考链接[^]*当前 `dev-flow` SKILL\.md 目录/);
    assert.match(content, /`docs\/`[^]*`myspec\/`[^]*仓库根目录/);
    assert.match(
      content,
      /名称缺失[^]*路径不存在[^]*不可读[^]*name[^]*不匹配[^]*多个入口[^]*停止[^]*缺口[^]*恢复/,
    );
    assert.equal(/[A-Z]:[\\\\/]/.test(content), false);
    assert.doesNotMatch(content, /[\\\\/]Users[\\\\/]/);

    const requirements = referenceContent[0];
    const implementation = referenceContent[1];
    const delivery = referenceContent[2];
    assert.match(requirements, /`subagent-policy`[^]*首次委派前/);
    assert.match(requirements, /Architect[^]*`codebase-design`[^]*实际使用/);
    assert.match(requirements, /`grill-with-docs`[^]*`grilling`[^]*`domain-modeling`/);
    assert.match(requirements, /Full[^]*`to-spec`[^]*`to-tickets`/);
    assert.match(requirements, /Fast[^]*`to-spec`[^]*`to-tickets`/);
    assertInOrder(requirements, "`to-spec`", "`to-tickets`");
    assert.match(implementation, /`subagent-policy`[^]*首次委派前/);
    assert.match(implementation, /`tdd`[^]*每[^]*票据[^]*红灯[^]*绿灯/);
    assert.match(implementation, /`build-and-verify`[^]*正式验证前/);
    assert.match(implementation, /`code-review`[^]*独立审查前/);
    assertInOrder(implementation, "`subagent-policy`", "`tdd`", "`build-and-verify`", "`code-review`");
    assert.match(delivery, /官方 `my-spec`[^]*实际调用/);
    assert.match(delivery, /需要规格变更[^]*`my-spec-add`[^]*实际调用/);
    assert.match(delivery, /门禁二授权后[^]*`pr-flow-complete`/);
    assert.match(delivery, /门禁二授权后[^]*需要规格变更[^]*`my-spec-add`[^]*`pr-flow-complete`/);
    assertInOrder(delivery, "预览", "门禁二授权后", "`my-spec-add`", "`pr-flow-complete`");
    assert.match(
      delivery,
      /进行中的 Git（版本管理）合并或变基冲突[^]*加载、读取和实际使用 `resolving-merge-conflicts`[^]*受影响的检查[^]*原失败步骤恢复/,
    );

    assert.ok(requirements.includes("`myspec/changes/<change-name>/spec.md`"));
    assert.ok(requirements.includes("`myspec/changes/<change-name>/issues/NN-<slug>.md`"));
    assert.match(requirements, /同一 change 目录[^]*issue-tracker/);
    for (const phrase of [
      "门禁一",
      "读取",
      "`spec.md`",
      "全部 `issues/*.md`",
      "命名",
      "状态",
      "顺序",
      "阻塞",
      "可观察范围",
      "测试接缝",
    ]) assert.ok(requirements.includes(phrase), `requirements missing ${phrase}`);
    assert.match(requirements, /缺失[^]*空白[^]*不一致[^]*停止/);
    for (const phrase of [
      "门禁二",
      "重新读取",
      "`spec.md`",
      "`issues/*.md`",
      "实际差异",
      "验证证据",
      "正式规格预览",
      "不一致",
      "停止",
    ]) assert.ok(delivery.includes(phrase), `delivery missing ${phrase}`);

    const changeRoot = resolve(repoRoot, "myspec", "changes", changeName);
    const spec = await readFile(resolve(changeRoot, "spec.md"), "utf8");
    const issueNames = (await readdir(resolve(changeRoot, "issues"))).sort();
    assert.deepEqual(issueNames, ["01-enforce-dependency-loading-and-change-artifacts.md"]);
    const issue = await readFile(resolve(changeRoot, "issues", issueNames[0]), "utf8");
    assert.match(spec, /可观察契约/);
    assert.match(spec, /MUST|必须/);
    assert.match(issue, /Status.*ready-for-agent/);
    assert.match(issue, /Blocked by.*None/);
    assert.match(issue, /验收条件|Acceptance criteria/);
    assert.ok(issue.includes("spec.md"));
    assert.ok(issue.includes("issues/NN-<slug>.md"));

    assert.match(referenceContent[0], /门禁一授权前保持只读[^]*沿用当前工作树和分支/);
    assert.match(referenceContent[2], /准确遗留项[^]*额外明确授权[^]*强制清理/);
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

    assert.match(
      referenceContent[1],
      /实施、返工和审查修复均不得修改或提交 `myspec\/specs\/`[^]*规格候选只能保存在目标工作树 `\.local\/spec-work\/`/,
    );
    assert.match(
      referenceContent[1],
      /主代理验收每次实施、返工或审查修复返回的实际文件、提交与差异时[^]*发现已跟踪或未跟踪的正式规格路径即判定 `REWORK_REQUIRED`[^]*不得接受票据/,
    );
    const specificationGateStep = implementationSteps?.match(/\n7\.\s+[^]*$/)?.[0];
    assert.ok(specificationGateStep, "缺少准备门禁二前的正式规格差异检查");
    const specificationDiffCommand =
      "`git diff --name-only <fixed-baseline> -- myspec/specs/`";
    const untrackedSpecificationCommand =
      "`git ls-files --others --exclude-standard -- myspec/specs/`";
    const diffCheckIndex = specificationGateStep.indexOf(specificationDiffCommand);
    const untrackedCheckIndex = specificationGateStep.indexOf(
      untrackedSpecificationCommand,
    );
    const deliveryLoadIndex = specificationGateStep.indexOf(
      "加载[规格与交付](delivery.md)",
    );
    assert.ok(diffCheckIndex >= 0, "缺少固定基线后的正式规格差异命令");
    assert.ok(untrackedCheckIndex >= 0, "缺少未跟踪正式规格文件检查");
    assert.ok(
      Math.max(diffCheckIndex, untrackedCheckIndex) < deliveryLoadIndex,
      "必须先检查全部正式规格差异再加载 delivery.md",
    );
    assert.match(specificationGateStep, /任一命令失败[^]*停止/);
    assert.match(
      specificationGateStep,
      /任一结果非空[^]*逐项列出[^]*停留实施阶段[^]*不准备门禁二[^]*不自动创建回退提交/,
    );
    assert.match(
      specificationGateStep,
      /结果均为空[^]*加载\[规格与交付\]\(delivery\.md\)/,
    );
    assert.match(referenceContent[2], /预览[^]*明确授权[^]*门禁二授权后[^]*原子应用/);
    assert.match(referenceContent[2], /完整差异[^]*引用[^]*不在门禁[^]*展开/);

    assert.match(referenceContent[0], /`subagent-policy`/);
    assert.match(referenceContent[0], /门禁一——开始开发/);
    assert.match(referenceContent[2], /门禁二——规格与交付/);
    assert.match(referenceContent[2], /完成检查不是第三个授权门禁/);
    assert.match(referenceContent[1], /同一 Git（版本管理）工作树[^]*同一非 `main` 分支/);
    assert.match(referenceContent[1], /可写调用严格串行/);
    assert.doesNotMatch(devFlowText, /Implementer（实施者）是唯一写入者|通过 Implementer（实施者）|交给 Implementer（实施者）|新的串行 Implementer（实施者）调用/);
    assert.match(content, /确认[^]*失败恢复[^]*持续有效/);
    assert.match(content, /“核心摘要”[^]*“确认后进入的下一步”/);
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
