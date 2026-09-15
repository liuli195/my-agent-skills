import assert from "node:assert/strict";
import { access, mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  DefaultResourceLoader,
  formatSkillsForPrompt,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packages = [
  {
    name: "plugin-sync",
    root: resolve(repoRoot, "plugins", "plugin-sync"),
    files: [
      "check.md",
      "status-taxonomy.md",
      "update-build-and-verify-runtime.md",
      "update-claude.md",
      "update-codex.md",
    ],
    references: ["check.md", "status-taxonomy.md", "update-claude.md", "update-codex.md"],
    description: /Synchronize local agent Plugin/,
  },
  {
    name: "retro-to-issues",
    root: resolve(repoRoot, "plugins", "retro-to-issues"),
    files: [],
    references: [],
    description: /总结会话或工作流问题/,
  },
];

function disclosedReferences(text) {
  return [...text.matchAll(/`references\/([^`]+)`/g)].map((match) => match[1]);
}

async function loadSkills() {
  const agentDir = await mkdtemp(resolve(tmpdir(), "shared-skills-"));
  const originalHome = process.env.HOME;
  const originalUserProfile = process.env.USERPROFILE;
  process.env.HOME = agentDir;
  process.env.USERPROFILE = agentDir;
  const settingsManager = SettingsManager.inMemory(
    { packages: packages.map(({ root }) => root) },
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
  try {
    await loader.reload();
    return { agentDir, loader };
  } catch (error) {
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
    if (originalUserProfile === undefined) delete process.env.USERPROFILE;
    else process.env.USERPROFILE = originalUserProfile;
    await rm(agentDir, { recursive: true, force: true });
    throw error;
  }
}

async function closeSkills(agentDir) {
  await rm(agentDir, { recursive: true, force: true });
}

test("Pi discovers both repository-owned pure Skill packages", async () => {
  const originalHome = process.env.HOME;
  const originalUserProfile = process.env.USERPROFILE;
  const { agentDir, loader } = await loadSkills();
  try {
    const result = loader.getSkills();
    for (const expected of packages) {
      const skill = result.skills.find(({ name }) => name === expected.name);
      assert.ok(skill, `missing ${expected.name}: ${JSON.stringify(result.diagnostics)}`);
      assert.equal(skill.sourceInfo.origin, "package");
      assert.equal(skill.sourceInfo.source, expected.root);
      assert.equal(skill.disableModelInvocation, false);
      assert.match(skill.description, expected.description);
      assert.match(
        formatSkillsForPrompt([skill]),
        new RegExp(`<name>${expected.name}</name>`),
      );

      const packageExtensions = loader
        .getExtensions()
        .extensions.filter(({ resolvedPath }) => resolvedPath.startsWith(expected.root));
      assert.deepEqual(packageExtensions, []);
      assert.deepEqual(await readdir(expected.root), ["skills"]);
      assert.deepEqual(await readdir(resolve(expected.root, "skills")), [expected.name]);

      const skillRoot = resolve(expected.root, "skills", expected.name);
      const entries = expected.references.length ? ["SKILL.md", "references"] : ["SKILL.md"];
      assert.deepEqual((await readdir(skillRoot)).sort(), entries.sort());
      if (expected.files.length) {
        assert.deepEqual(
          (await readdir(resolve(skillRoot, "references"))).sort(),
          expected.files.sort(),
        );
      }
      const content = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");
      assert.deepEqual(disclosedReferences(content).sort(), expected.references.sort());
      for (const reference of expected.references) {
        await access(resolve(skillRoot, "references", reference));
        assert.match(content, new RegExp(`references/${reference.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`));
      }
    }
  } finally {
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
    if (originalUserProfile === undefined) delete process.env.USERPROFILE;
    else process.env.USERPROFILE = originalUserProfile;
    await closeSkills(agentDir);
  }
});

test("Retro To Issues keeps the review confirmation boundary", async () => {
  const content = await readFile(
    resolve(repoRoot, "plugins", "retro-to-issues", "skills", "retro-to-issues", "SKILL.md"),
    "utf8",
  );
  assert.match(content, /只在用户审阅后写入/);
  assert.match(content, /此步骤只读。不要创建、评论、重新打开、关闭、编辑或打标签。/);
  assert.match(content, /用户确认前，不写入 GitHub。/);
  assert.ok(
    content.indexOf("用户确认前，不写入 GitHub。") < content.indexOf("9. 写入已确认记录"),
  );
});
