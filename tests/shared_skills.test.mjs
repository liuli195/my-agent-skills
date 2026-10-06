import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const packages = [
  {
    name: "plugin-sync",
    root: resolve(repoRoot, "plugins", "plugin-sync"),
    files: [
      "check.md",
      "status-taxonomy.md",
      "switch-source.md",
      "update-build-and-verify-runtime.md",
      "update-claude.md",
      "update-codex.md",
    ],
    references: ["check.md", "status-taxonomy.md", "update-claude.md", "update-codex.md", "switch-source.md"],
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

test("repository-owned pure Skill packages keep their portable contracts", async () => {
  for (const expected of packages) {
    const frontmatter = (await readFile(resolve(expected.root, "skills", expected.name, "SKILL.md"), "utf8")).split("---")[1];
    assert.match(frontmatter, new RegExp(`^name: ${expected.name}$`, "m"));
    assert.doesNotMatch(frontmatter, /^disable-model-invocation: true$/m);
    assert.match(frontmatter, expected.description);
    assert.deepEqual((await readdir(expected.root)).sort(), [".claude-plugin", ".codex-plugin", "skills"]);
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
