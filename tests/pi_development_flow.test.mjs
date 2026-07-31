import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

import {
  DefaultResourceLoader,
  formatSkillsForPrompt,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = resolve(repoRoot, "plugins", "pi-development-flow");
const skillRoot = resolve(pluginRoot, "skills", "pi-development-flow");
const execFileAsync = promisify(execFile);

const references = [
  "initialization.md",
  "requirements.md",
  "implementation.md",
  "delivery.md",
  "resume.md",
];

test("requirements stop unless the exact discussion skills are loaded", async () => {
  const requirements = await readFile(
    resolve(skillRoot, "references", "requirements.md"),
    "utf8",
  );
  const mustBlock = requirements.match(/## MUST[^]*?(?=\n## )/)?.[0];

  assert.ok(mustBlock, "missing requirements MUST block");
  assert.match(mustBlock, /`grill-with-docs`/);
  assert.match(mustBlock, /`domain-modeling`/);
  assert.match(mustBlock, /MUST NOT.*`grilling`/);
  assert.match(mustBlock, /stop/i);
  assert.match(mustBlock, /tool-call evidence/i);
});

test("implementation keeps direct work optional and delegated work ticket-scoped", async () => {
  const implementation = await readFile(
    resolve(skillRoot, "references", "implementation.md"),
    "utf8",
  );

  assert.match(implementation, /MAY implement sequential tickets directly/i);
  assert.match(implementation, /does not require delegation/i);
  assert.match(implementation, /each Implementer invocation MUST bind exactly one published ticket/i);
  assert.match(implementation, /MUST NOT combine multiple published tickets/i);
  assert.match(implementation, /accepted before the next sequential ticket/i);
});

test("implementation requires tool-enforced cwd for writable delegation", async () => {
  const implementation = await readFile(
    resolve(skillRoot, "references", "implementation.md"),
    "utf8",
  );

  assert.match(implementation, /`dispatch_implementer_in_worktree`/);
  assert.match(implementation, /MUST NOT rely on a prompt to change directories/i);
  assert.match(implementation, /stop before delegation.*handoff/i);
});

test("worktree dispatch binds Implementer to one verified non-primary worktree", async () => {
  const root = await mkdtemp(join(tmpdir(), "pi-development-flow-dispatch-"));
  const worktree = join(root, "feature");
  try {
    await execFileAsync("git", ["init", "-b", "main", root]);
    await execFileAsync("git", ["-C", root, "config", "user.email", "test@example.com"]);
    await execFileAsync("git", ["-C", root, "config", "user.name", "Test User"]);
    await execFileAsync("git", ["-C", root, "commit", "--allow-empty", "-m", "initial"]);
    await execFileAsync("git", ["-C", root, "worktree", "add", "-b", "feature", worktree]);
    const ticketPath = join(
      worktree,
      "myspec",
      "changes",
      "smoke",
      "issues",
      "01-marker.md",
    );
    await mkdir(dirname(ticketPath), { recursive: true });
    await writeFile(ticketPath, "# 01 Marker\n\n- 状态：ready-for-agent\n", "utf8");

    const listeners = new Map();
    const tools = new Map();
    const events = {
      on(name, handler) {
        const handlers = listeners.get(name) ?? new Set();
        handlers.add(handler);
        listeners.set(name, handlers);
        return () => handlers.delete(handler);
      },
      emit(name, data) {
        for (const handler of listeners.get(name) ?? []) handler(data);
      },
    };
    let spawnRequest;
    let completeSpawn = true;
    events.on("subagents:rpc:ping", ({ requestId }) => {
      events.emit(`subagents:rpc:ping:reply:${requestId}`, {
        success: true,
        data: { version: 2 },
      });
    });
    events.on("subagents:rpc:spawn", (request) => {
      spawnRequest = request;
      events.emit(`subagents:rpc:spawn:reply:${request.requestId}`, {
        success: true,
        data: { id: "agent-1" },
      });
      if (completeSpawn) {
        setImmediate(() => events.emit("subagents:completed", {
          id: "agent-1",
          status: "completed",
          result: "implemented",
        }));
      }
    });
    events.on("subagents:rpc:stop", ({ requestId }) => {
      events.emit(`subagents:rpc:stop:reply:${requestId}`, { success: true });
    });

    const pi = {
      events,
      registerTool(tool) { tools.set(tool.name, tool); },
      async exec(command, args, options) {
        const result = await execFileAsync(command, args, {
          cwd: options?.cwd,
          signal: options?.signal,
          timeout: options?.timeout,
        });
        return { stdout: result.stdout, stderr: result.stderr, code: 0, killed: false };
      },
    };
    const extensionUrl = pathToFileURL(
      resolve(pluginRoot, "extensions", "dispatch.ts"),
    ).href;
    const { registerWorktreeDispatch } = await import(extensionUrl);
    registerWorktreeDispatch(pi, {}, 10);

    const tool = tools.get("dispatch_implementer_in_worktree");
    assert.ok(tool, "missing worktree dispatch tool");
    const result = await tool.execute(
      "call-1",
      { worktree_path: worktree, expected_branch: "feature", ticket_path: ticketPath },
      undefined,
      undefined,
      { cwd: root },
    );

    assert.equal(spawnRequest.type, "Implementer");
    assert.equal(spawnRequest.options.cwd, worktree);
    assert.equal(spawnRequest.options.isolated, true);
    assert.match(spawnRequest.prompt, /myspec[\\/]changes[\\/]smoke[\\/]issues[\\/]01-marker\.md/);
    assert.doesNotMatch(spawnRequest.prompt, /Implement ticket 03/);
    assert.equal(result.details.branch, "feature");
    assert.equal(result.details.result, "implemented");
    await assert.rejects(
      tool.execute(
        "call-2",
        { worktree_path: worktree, expected_branch: "wrong", ticket_path: ticketPath },
        undefined,
        undefined,
        { cwd: root },
      ),
      /expected branch/i,
    );
    await assert.rejects(
      tool.execute(
        "call-3",
        { worktree_path: root, expected_branch: "main", ticket_path: ticketPath },
        undefined,
        undefined,
        { cwd: root },
      ),
      /primary worktree/i,
    );

    completeSpawn = false;
    await assert.rejects(
      tool.execute(
        "call-4",
        { worktree_path: worktree, expected_branch: "feature", ticket_path: ticketPath },
        undefined,
        undefined,
        { cwd: root },
      ),
      /timed out/i,
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("delivery excludes unrequested installation, synchronization, and release work", async () => {
  const delivery = await readFile(
    resolve(skillRoot, "references", "delivery.md"),
    "utf8",
  );
  const skill = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");

  assert.match(delivery, /By default, Development Flow excludes local installation/i);
  assert.match(delivery, /MUST NOT proactively list or ask/i);
  assert.match(delivery, /only when the user explicitly requests that exact action/i);
  assert.match(delivery, /continue (?:the )?cleanup.*does not authorize/i);
  assert.match(delivery, /unrequested.*MUST NOT block completion/i);
  assert.doesNotMatch(skill, /authorized local delivery is verified/i);
});

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
      noExtensions: false,
      noPromptTemplates: true,
      noThemes: true,
      noContextFiles: true,
    });
    await loader.reload();

    const extensions = loader.getExtensions().extensions;
    assert.ok(
      extensions.some(({ resolvedPath }) => resolvedPath.endsWith("pi-development-flow.ts")),
      `missing pi-development-flow extension: ${JSON.stringify(loader.getExtensions().errors)}`,
    );

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
