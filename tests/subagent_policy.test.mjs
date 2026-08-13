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
  "主代理决定是否委派以及何时委派。",
  "每个会话在首次委派前检查一次有效宿主配置。",
  "只启用下列四个角色",
  "活跃模型注册表",
  "| Explorer（调查者） | 以只读方式执行被委派的搜索、研究和证据收集。 | `openai-codex/gpt-5.6-luna` | `low`（低） | 读取、搜索、只读 Shell（命令行）命令和网页搜索 |",
  "| Implementer（实施者） | 根据已确认需求实施被委派的代码或文档。 | `openai-codex/gpt-5.6-luna` | `max`（最高） | 完整实施工具；禁用扩展；预加载 TDD（测试驱动开发） |",
  "| Reviewer（审查者） | 根据需求和仓库规则，独立审查被委派的代码或文档。 | `openai-codex/gpt-5.6-sol` | `medium`（中等） | 读取、搜索和只读 Shell（命令行）命令 |",
  "| Architect（架构师） | 以只读方式调查架构、架构决策和疑难缺陷诊断。 | `openai-codex/gpt-5.6-sol` | `max`（最高） | 读取、搜索和只读 Shell（命令行）命令 |",
  "prompt_mode: append",
  "extensions: false",
  "skills: tdd",
  "实施功能、缺陷或集成行为前使用 `/skill:tdd`（测试驱动开发技能）；遵循红灯到绿灯循环",
  "以只读方式调查被委派的问题，并返回简洁的发现、证据、来源位置和不确定项。",
  "独立审查被委派的代码或文档范围；报告包含严重程度和证据、可采取行动的发现。",
  "以只读方式调查架构、架构决策或疑难缺陷诊断。",
  "只有每个字段都完全匹配时，才允许选择相应的宿主原生角色。",
  "如果任一字段不同、无法证明，或者宿主没有经过验证的 host Adapter（宿主适配器），则在委派前停止。",
  "主代理在依赖其结果或宣告工作完成前，必须验证子代理的实际结果。",
];

test("Pi discovers the independent subagent-policy skill package and its fixed contract", async () => {
  const agentDir = await mkdtemp(join(tmpdir(), "subagent-policy-"));
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
    const skill = result.skills.find(({ name }) => name === "subagent-policy");
    assert.ok(skill, `missing subagent-policy: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, packageRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /委派任何子代理前/);
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
    const headings = [...content.matchAll(/^## (.+)$/gm)].map((match) => match[1]);
    assert.deepEqual(
      headings,
      ["MUST — 必须依赖", "流程编排"],
      "必须且只能依次包含两个顶层编排模块",
    );
    assert.match(content, /## 流程编排[^]*宿主没有经过验证的 host Adapter（宿主适配器）[^]*在委派前停止/s);
    assert.doesNotMatch(content, /\bClaude\b|\bCodex\b/);
  } finally {
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
    if (originalUserProfile === undefined) delete process.env.USERPROFILE;
    else process.env.USERPROFILE = originalUserProfile;
    await rm(agentDir, { recursive: true, force: true });
  }
});
