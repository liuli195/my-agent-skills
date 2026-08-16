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
  "主 Agent（代理）决定是否委派、何时委派以及调用几个角色。",
  "| Explorer（调查者） | 搜索、研究并收集证据。 | `gpt-5.6-luna` | `low`（低） | 只读 |",
  "| Implementer（实施者） | 根据已确认需求修改代码或文档并验证结果。 | `gpt-5.6-luna` | `max`（最高） | 可写 |",
  "| Reviewer（审查者） | 根据需求和仓库规则独立审查代码或文档。 | `gpt-5.6-sol` | `medium`（中等） | 只读 |",
  "| Architect（架构师） | 调查架构、架构决策和疑难缺陷。 | `gpt-5.6-sol` | `max`（最高） | 只读 |",
  "无法使用指定模型或思考强度时，不以其他配置冒充该角色",
  "只有 Implementer（实施者）可以在明确授权范围内写入。",
  "使用宿主现有的通用或具名子代理入口，不要求特定工具或配置格式。",
  "每次提示词都写明角色、具体目标、范围与非目标、已有证据、读写边界和预期返回内容。",
  "行为变更先使用可用的 TDD（测试驱动开发）Skill（技能）完成红灯到绿灯循环",
  "主 Agent（代理）在依赖结果或宣告完成前，核验实际文件、差异、版本管理状态和检查结果",
];

test("host discovers the independent subagent-policy skill package and its portable contract", async () => {
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
    assert.match(skill.description, /四个通用子代理角色/);
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
      ["角色契约", "主代理决策", "委派提示词", "结果验收"],
      "必须依次定义角色、决策、提示词和验收",
    );
    assert.doesNotMatch(content, /prompt_mode|extensions: false|host Adapter|活跃模型注册表|默认代理已禁用/);
    assert.doesNotMatch(content, /\bPi\b|\bClaude\b|\bCodex\b/);
  } finally {
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
    if (originalUserProfile === undefined) delete process.env.USERPROFILE;
    else process.env.USERPROFILE = originalUserProfile;
    await rm(agentDir, { recursive: true, force: true });
  }
});
