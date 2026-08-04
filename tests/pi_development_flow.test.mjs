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
  "output-template.md",
  "resume.md",
];

function section(text, start, end = /\n## /) {
  const offset = text.search(start);
  assert.notEqual(offset, -1, `missing ${start}`);
  const tail = text.slice(offset);
  const endOffset = tail.slice(1).search(end);
  return endOffset === -1 ? tail : tail.slice(0, endOffset + 1);
}

const gateFields = [
  "Usage Condition（使用条件）",
  "Previous Gate（上一依赖门禁）",
  "Checks（检查清单）",
  "Confirmation Output（待用户确认内容清单）",
  "Next Gate（下一步门禁）",
];

test("primary stages declare dependencies and their gate state before execution", async () => {
  const documents = Object.fromEntries(await Promise.all(
    ["requirements.md", "implementation.md", "delivery.md"].map(async (name) => [
      name,
      await readFile(resolve(skillRoot, "references", name), "utf8"),
    ]),
  ));

  for (const [name, text] of Object.entries(documents)) {
    const dependenciesAt = text.indexOf("## MUST — Dependencies（依赖）");
    const gateAt = text.indexOf("## MUST — Gate（门禁）");
    const firstOrdinarySectionAt = text.search(/\n## (?!MUST)/);
    assert.ok(dependenciesAt > 0, `${name} is missing its dependencies block`);
    assert.ok(gateAt > dependenciesAt, `${name} is missing its gate block`);
    assert.ok(gateAt < firstOrdinarySectionAt, `${name} declares its gate after execution starts`);
  }

  const requirementsDependencies = section(
    documents["requirements.md"],
    /## MUST — Dependencies（依赖）/,
  );
  assert.match(requirementsDependencies, /`codebase-design`/);
  assert.match(requirementsDependencies, /`grill-with-docs`/);
  assert.match(requirementsDependencies, /`domain-modeling`/);
  assert.match(requirementsDependencies, /`to-spec`/);
  assert.match(requirementsDependencies, /`to-tickets`/);
  assert.match(requirementsDependencies, /MUST NOT.*`grilling`/);
  assert.ok(
    requirementsDependencies.indexOf("`codebase-design`")
      < requirementsDependencies.indexOf("`grill-with-docs`"),
    "requirements must design before grilling",
  );
  assert.match(
    requirementsDependencies,
    /Before invoking `to-spec` or `to-tickets`[^]*current-session tool-call evidence that `codebase-design`, `grill-with-docs`, and `domain-modeling` were read/,
  );

  for (const text of Object.values(documents)) assert.match(text, /output-template\.md/);

  const requirements = documents["requirements.md"];
  assert.match(
    requirements,
    /Direction Confirmation.*not a formal gate[^]*does not publish artifacts or authorize implementation or delivery/is,
  );
  assert.match(requirements, /only.*unresolved.*detail/i);
  assert.match(
    requirements,
    /Return to the overall design proposal when an answer changes the scope, Module（模块）, Interface（接口）, Seam（接缝）, highest public test seam, or Flow Level（流程等级）; otherwise continue with the unresolved detail\./,
  );

  const implementationDependencies = section(
    documents["implementation.md"],
    /## MUST — Dependencies（依赖）/,
  );
  assert.match(implementationDependencies, /`tdd`/);
  assert.match(implementationDependencies, /`build-and-verify`/);
  assert.match(implementationDependencies, /`code-review`/);
  assert.match(implementationDependencies, /`pi-subagent-policy`.*delegat/is);

  const deliveryDependencies = section(
    documents["delivery.md"],
    /## MUST — Dependencies（依赖）/,
  );
  assert.match(deliveryDependencies, /`my-spec-add`/);
  assert.match(deliveryDependencies, /`pr-flow-complete`/);
  assert.match(deliveryDependencies, /`pr-flow-tweak`/);
  assert.match(deliveryDependencies, /`resolving-merge-conflicts`/);
});

test("the three gates form the required stage state machine", async () => {
  const skill = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");
  for (const name of [
    "Gate 1 — Requirements Confirmation（需求确认）",
    "Gate 2 — Implementation and Verification（实施和验证）",
    "Gate 3 — Specification Archival and Delivery（规格存档并交付）",
    "Completion Check — 完成检查",
  ]) assert.match(skill, new RegExp(name));
  assert.doesNotMatch(skill, /Gate 4 —/);

  const ownership = [
    ["requirements.md", 1, "Requirements Confirmation"],
    ["implementation.md", 2, "Implementation and Verification"],
    ["delivery.md", 3, "Specification Archival and Delivery"],
  ];

  for (const [name, number, gateName] of ownership) {
    const text = await readFile(resolve(skillRoot, "references", name), "utf8");
    const gate = section(
      text,
      new RegExp(`### Gate ${number} — ${gateName}[^\\n]*`),
      /\n### Gate |\n## /,
    );
    for (const field of gateFields) assert.match(gate, new RegExp(`#### ${field}`));
  }

  const requirements = await readFile(resolve(skillRoot, "references", "requirements.md"), "utf8");
  const implementation = await readFile(resolve(skillRoot, "references", "implementation.md"), "utf8");
  const delivery = await readFile(resolve(skillRoot, "references", "delivery.md"), "utf8");
  assert.match(
    section(requirements, /### Gate 1 — Requirements Confirmation/, /\n### Gate |\n## /),
    /Gate 2 — Implementation and Verification/,
  );
  assert.match(
    section(implementation, /### Gate 2 — Implementation and Verification/, /\n### Gate |\n## /),
    /Gate 1 — Requirements Confirmation[^]*Gate 3 — Specification Archival and Delivery/,
  );
  const gate3 = section(
    delivery,
    /### Gate 3 — Specification Archival and Delivery/,
    /\n### Gate |\n## /,
  );
  assert.match(gate3, /Gate 2 — Implementation and Verification/);
  assert.match(gate3, /Completion Check — 完成检查/);
  assert.match(gate3, /`my-spec-add`[^]*final confirmation/is);
  assert.match(
    gate3,
    /Gate 3 passes only after[^]*appl(?:y|ies|ication)[^]*validat/is,
  );
  assert.match(gate3, /Development Flow summary uses.*output-template/is);
  assert.match(gate3, /detailed final confirmation.*exact.*output/is);
  assert.match(gate3, /delivery authorization/is);
  assert.doesNotMatch(gate3, /After Gate 3 .* passes, run `my-spec-add`/);
  assert.doesNotMatch(delivery, /Gate 4 —/);
});

test("gate outputs use one exact four-section template", async () => {
  const template = await readFile(resolve(skillRoot, "references", "output-template.md"), "utf8");
  const skill = await readFile(resolve(skillRoot, "SKILL.md"), "utf8");
  const headings = [
    "### 状态与待确认",
    "### 核心内容摘要",
    "### 引用",
    "### 下一步",
  ];
  assert.deepEqual(
    [...template.matchAll(/^### .*$/gm)].map(({ 0: heading }) => heading),
    headings,
  );
  for (const name of headings) assert.match(template, new RegExp(`^${name}$`, "m"));
  assert.match(template, /Gate 1 — Requirements Confirmation（需求确认）/);
  assert.match(template, /Gate 2 — Implementation and Verification（实施和验证）/);
  assert.match(template, /Gate 3 — Specification Archival and Delivery（规格存档并交付）/);
  assert.doesNotMatch(template, /Gate 4 —/);
  assert.match(template, /Completion Check — 完成检查/);
  assert.match(template, /Gate 1：目标、范围、测试接缝、票据及阻塞关系、变更工作树/);
  assert.match(template, /Gate 2：票据顺序、并行组、执行隔离、验证、审查、风险和停止条件/);
  assert.match(template, /Gate 3：正式规格差异、校验结果、已知风险和准确交付动作/);
  assert.match(template, /Completion Check：完成条件、实际状态和清理残留/);
  assert.match(skill, /references\/output-template\.md/);
});

test("completion check distinguishes final completion from cleanup residue", async () => {
  const delivery = await readFile(
    resolve(skillRoot, "references", "delivery.md"),
    "utf8",
  );
  const completion = section(
    delivery,
    /### Completion Check — 完成检查/,
    /\n### Gate |\n## /,
  );

  assert.match(completion, /Gate 3 — Specification Archival and Delivery/);
  assert.match(completion, /final completion|最终完成/i);
  assert.match(completion, /cleanup residue|清理残留/i);
  assert.match(completion, /physical worktree directory|实体工作树目录/i);
  assert.match(completion, /exact path|精确路径/i);
  assert.match(completion, /cleanup reason|清理原因/i);
  assert.match(completion, /citation evidence|引用证据/i);
  assert.match(completion, /force cleanup|强制清理/i);
  assert.match(completion, /explicit authorization|明确授权/i);
  assert.match(completion, /refusal.*residue.*recovery|拒绝.*残留.*恢复/is);
  assert.match(completion, /authorization.*check.*again|授权.*再次.*检查/is);
  assert.match(completion, /not.*fourth.*gate|不新增第四个正式授权门禁/is);
  assert.match(completion, /unrequested.*(?:not|does not).*block|未请求.*不.*阻塞/is);
  assert.match(completion, /output-template\.md/);
});

test("initialization and resume route through the three gates without MUST blocks", async () => {
  const initialization = await readFile(
    resolve(skillRoot, "references", "initialization.md"),
    "utf8",
  );
  const resume = await readFile(resolve(skillRoot, "references", "resume.md"), "utf8");

  assert.doesNotMatch(initialization, /^## MUST/m);
  assert.match(initialization, /`codebase-design`/);
  assert.match(initialization, /`grilling`/);
  assert.match(initialization, /not a fourth.*gate/i);
  assert.match(initialization, /return.*same gate/i);
  assert.match(initialization, /formal entr/i);

  assert.doesNotMatch(resume, /^## MUST/m);
  assert.match(resume, /previous passed gate/i);
  assert.match(resume, /current gate.*next gate/i);
  assert.match(resume, /stage document.*dependencies/i);
  assert.match(resume, /continue.*resume.*not.*authoriz/is);
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

test("direct Agent dispatch blocks writable and unknown roles but allows read-only roles", async () => {
  const listeners = new Map();
  const pi = {
    on(name, handler) {
      listeners.set(name, handler);
    },
    registerTool() {},
  };
  const dispatchUrl = pathToFileURL(
    resolve(pluginRoot, "extensions", "dispatch.ts"),
  ).href;
  const { registerDirectAgentGuard } = await import(dispatchUrl);
  registerDirectAgentGuard(pi);

  const guard = listeners.get("tool_call");
  assert.ok(guard, "missing direct Agent guard");
  const call = (input, toolName = "Agent") => guard({ toolName, input }, {});

  for (const role of ["Implementer", "unknown", ""]) {
    const result = await call({ subagent_type: role });
    assert.equal(result?.block, true, `expected ${role || "empty"} role to be blocked`);
    assert.match(result?.reason ?? "", /dispatch_implementer_in_worktree/);
  }
  const resumed = await call({ subagent_type: "Explorer", resume: "agent-1" });
  assert.equal(resumed?.block, true);

  for (const role of ["Explorer", "Reviewer", "Architect", "explorer"]) {
    assert.equal(await call({ subagent_type: role }), undefined, `${role} should be allowed`);
  }
  assert.equal(await call({ subagent_type: "Implementer" }, "other_tool"), undefined);
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
    await writeFile(ticketPath, "# 01 Marker\n", "utf8");
    const invalidTicketPath = join(worktree, "myspec", "changes", "smoke", "spec.md");
    await writeFile(invalidTicketPath, "# Not a ticket\n", "utf8");

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
    let stopRequest;
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
    events.on("subagents:rpc:stop", (request) => {
      stopRequest = request;
      events.emit(`subagents:rpc:stop:reply:${request.requestId}`, { success: true });
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
    assert.equal(spawnRequest.options.isolated, false);
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
    await assert.rejects(
      tool.execute(
        "call-invalid-ticket",
        {
          worktree_path: worktree,
          expected_branch: "feature",
          ticket_path: invalidTicketPath,
        },
        undefined,
        undefined,
        { cwd: root },
      ),
      /published ticket/i,
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
    assert.equal(stopRequest.agentId, "agent-1");
    assert.equal(listeners.get("subagents:completed")?.size ?? 0, 0);
    assert.equal(listeners.get("subagents:failed")?.size ?? 0, 0);
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
    const flowExtension = extensions.find(({ resolvedPath }) => resolvedPath.endsWith("pi-development-flow.ts"));
    assert.ok(
      flowExtension,
      `missing pi-development-flow extension: ${JSON.stringify(loader.getExtensions().errors)}`,
    );
    assert.ok(flowExtension.handlers.has("tool_call"), "missing direct Agent guard handler");
    assert.deepEqual(loader.getExtensions().errors, []);

    const result = loader.getSkills();
    const skill = result.skills.find(({ name }) => name === "pi-development-flow");
    assert.ok(skill, `missing pi-development-flow: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(skill.sourceInfo.origin, "package");
    assert.equal(skill.sourceInfo.source, pluginRoot);
    assert.equal(skill.disableModelInvocation, false);
    assert.match(skill.description, /development change/i);
    assert.match(skill.description, /design-first requirements/i);
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
