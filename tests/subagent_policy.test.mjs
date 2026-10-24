import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packageRoot = resolve(repoRoot, "plugins", "subagent-policy");
const skillRoot = resolve(packageRoot, "skills", "subagent-policy");
const skillPath = resolve(skillRoot, "SKILL.md");

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const contract = [
  "主 Agent（代理）决定是否委派、何时委派以及调用几个角色。",
  "| Explorer（调查者） | 搜索、研究并收集证据。 | `gpt-6-luna` | `low`（低） | 只读 |",
  "| Implementer（实施者） | 根据已确认需求修改代码或文档并验证结果。 | `gpt-6.1-sol` | `medium`（中） | 可写 |",
  "| Reviewer（审查者） | 根据需求和仓库规则独立审查代码或文档。 | `gpt-6.1-sol` | `high`（高） | 只读 |",
  "| Architect（架构师） | 调查架构、架构决策和疑难缺陷。 | `gpt-6-sol` | `xhigh`（超高） | 只读 |",
  "无法使用指定模型或思考强度时，改用宿主默认的模型和思考强度承载同一角色",
  "四个角色默认使用宿主已配置的具名代理；宿主不支持具名代理时，才显式回退到通用代理，并声明具名代理不可用、实际配置和同等读写边界",
  "只读角色的具名代理若实际边界被宿主或父会话覆盖，仍使用该具名代理完成只读任务，并明确声明“只读边界回退”、实际权限和未执行的写入限制；这不是通用代理回退",
  "子代理中只有 Implementer（实施者）可以在明确授权范围内写入。",
  "主 Agent（代理）确认票据无依赖、改动范围和测试资源互不冲突后，可在同一工作区并行委派可写 Implementer（实施者）",
  "共享 Git（版本管理）操作由主 Agent（代理）串行执行",
  "使用宿主已配置的具名代理入口；回退按上述规则处理",
  "每次提示词都写明角色、具体目标、范围与非目标、已有证据、读写边界和预期返回内容。",
  "行为变更先使用可用的 TDD（测试驱动开发）Skill（技能）完成红灯到绿灯循环",
  "主 Agent（代理）在依赖结果或宣告完成前，核验实际文件、差异、版本管理状态和检查结果",
];

test("subagent-policy keeps its portable Skill contract and directory structure", async () => {
    const frontmatter = (await readFile(resolve(skillRoot, "SKILL.md"), "utf8")).split("---")[1];
    assert.match(frontmatter, /^name: subagent-policy$/m);
    assert.doesNotMatch(frontmatter, /^disable-model-invocation: true$/m);
    assert.match(frontmatter, /四个通用子代理角色/);
    assert.deepEqual((await readdir(packageRoot)).sort(), [".claude-plugin", ".codex-plugin", "skills"]);
    assert.deepEqual(await readdir(resolve(packageRoot, "skills")), ["subagent-policy"]);
    assert.deepEqual(await readdir(skillRoot), ["SKILL.md"]);

    const content = await readFile(skillPath, "utf8");
    for (const text of contract) assert.match(content, new RegExp(escapeRegExp(text)));
    assert.match(
      content,
      /无法使用指定模型或思考强度时[^]*承载同一角色/,
      "模型或思考强度不可用时必须改用宿主默认配置承载同一角色，而不是放弃角色",
    );
    assert.match(
      content,
      /不得改用主 Agent（代理）自行完成/,
      "回退不得削弱角色结构",
    );
    assert.doesNotMatch(
      content,
      /由主 Agent（代理）自行完成或报告差异/,
      "旧的放弃子代理回退必须被替换",
    );
    const headingMatches = [...content.matchAll(/^## (.+)$/gm)];
    const sectionBody = (title) => {
      const index = headingMatches.findIndex((heading) => heading[1] === title);
      assert.notEqual(index, -1, `缺少小节：${title}`);
      const start = headingMatches[index].index + headingMatches[index][0].length;
      const end = index + 1 < headingMatches.length ? headingMatches[index + 1].index : content.length;
      return content.slice(start, end);
    };
    assert.match(
      sectionBody("委派提示词"),
      /回退/,
      "委派提示词小节必须要求声明回退，否则主代理照清单执行不会带出它",
    );
    assert.match(
      sectionBody("结果验收"),
      /回退/,
      "结果验收小节必须把未声明回退列为不予接受的情况",
    );
    assert.match(content, /只读边界回退/);
    assert.match(content, /这不是通用代理回退/);
    const headings = headingMatches.map((match) => match[1]);
    assert.deepEqual(
      headings,
      ["角色契约", "主代理决策", "委派提示词", "结果验收"],
      "必须依次定义角色、决策、提示词和验收",
    );
    assert.doesNotMatch(content, /prompt_mode|extensions: false|host Adapter|活跃模型注册表|默认代理已禁用/);
    assert.doesNotMatch(content, /\bPi\b|\bClaude\b|\bCodex\b/);
});
