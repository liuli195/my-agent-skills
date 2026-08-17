import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = resolve(repoRoot, "plugins", "orca-ntfy", "orca-plugin.json");
const pluginUrl = pathToFileURL(resolve(repoRoot, "plugins", "orca-ntfy", "main.mjs")).href;
const defaultSecrets = {
  "ntfy-topic": "random-topic-7f2c",
  "ntfy-token": "token-only-for-tests",
};

async function loadActivate() {
  const module = await import(pluginUrl);
  assert.equal(typeof module.default, "function");
  return module.default;
}

function createOrca(secretValues = {}) {
  let listener;
  const secrets = { ...defaultSecrets, ...secretValues };
  const secretCalls = [];
  const orca = {
    events: {
      on(name, handler) {
        assert.equal(name, "agent.status.changed");
        listener = handler;
      },
    },
    host: {
      async call(name, args) {
        secretCalls.push({ name, args });
        assert.equal(name, "secrets.get");
        return { value: secrets[args.key] };
      },
    },
  };
  return {
    orca,
    secretCalls,
    emit(event) {
      assert.equal(typeof listener, "function");
      return listener(event);
    },
  };
}

function stateEvent(state, overrides = {}) {
  return {
    worktreeId: "C:\\private\\workspace",
    paneKey: "pane-1",
    state,
    output: "private agent output",
    ...overrides,
  };
}

function installNetwork(responses) {
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  const requests = [];
  const delays = [];
  let index = 0;
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    const response = responses[Math.min(index++, responses.length - 1)];
    if (response instanceof Error) throw response;
    return response;
  };
  globalThis.setTimeout = (callback, delay, ...args) => {
    delays.push(delay);
    callback(...args);
    return 0;
  };
  return {
    requests,
    delays,
    restore() {
      globalThis.fetch = originalFetch;
      globalThis.setTimeout = originalSetTimeout;
    },
  };
}

async function captureErrors(callback) {
  const originalError = console.error;
  const logs = [];
  console.error = (...args) => logs.push(args.join(" "));
  try {
    await callback();
  } finally {
    console.error = originalError;
  }
  return logs;
}

const successfulResponse = { ok: true, status: 204 };

test("清单声明最小 Orca 事件与私密能力", async () => {
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));

  assert.equal(manifest.manifestVersion, 1);
  assert.equal(manifest.id, "ntfy-notifications");
  assert.equal(manifest.publisher, "liuli195");
  assert.equal(manifest.name, "Orca ntfy notifications");
  assert.equal(manifest.version, "1.0.2");
  assert.equal(manifest.engines.orca, ">=1.4.0");
  assert.equal(manifest.pluginApi, 1);
  assert.equal(manifest.main, "main.mjs");
  assert.deepEqual(manifest.contributes.events, [{ on: "agent.status.changed" }]);
  assert.deepEqual(manifest.capabilities, [{ kind: "events:subscribe" }, { kind: "secrets" }]);
  assert.equal(manifest.capabilities.some(({ kind }) => kind === "net:fetch"), false);
});

test("公共匿名发布只读取主题且不发送授权请求头", async () => {
  const activate = await loadActivate();
  const harness = createOrca({ "ntfy-token": "legacy-token-present" });
  const network = installNetwork([successfulResponse]);
  try {
    await activate(harness.orca);
    await harness.emit(stateEvent("blocked"));

    assert.deepEqual(
      harness.secretCalls.map(({ name, args }) => ({ name, key: args.key })),
      [{ name: "secrets.get", key: "ntfy-topic" }],
    );
    assert.equal(Object.hasOwn(network.requests[0].options.headers, "Authorization"), false);
  } finally {
    network.restore();
  }
});

for (const [state, body, priority] of [
  ["blocked", "会话阻塞，等待处理", "high"],
  ["waiting", "会话已完成，等待回复", "high"],
  ["done", "会话已经彻底完成", "default"],
]) {
  test(`${state} 状态从真实入口发送固定通知`, async () => {
    const activate = await loadActivate();
    const harness = createOrca();
    const network = installNetwork([successfulResponse]);
    try {
      await activate(harness.orca);
      await harness.emit(stateEvent(state));

      assert.equal(network.requests.length, 1);
      assert.deepEqual(network.requests[0], {
        url: "https://ntfy.sh/random-topic-7f2c",
        options: {
          method: "POST",
          headers: {
            Title: "orca agent",
            Priority: priority,
            Tags: state,
            "Content-Type": "text/plain",
          },
          body,
        },
      });
    } finally {
      network.restore();
    }
  });
}

test("未知状态忽略且不占用后续支持状态的去重记录", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const network = installNetwork([successfulResponse]);
  try {
    await activate(harness.orca);
    await harness.emit(stateEvent("running"));
    await harness.emit(stateEvent("__proto__"));
    assert.equal(network.requests.length, 0);
    assert.deepEqual(harness.secretCalls, []);

    await harness.emit(stateEvent("blocked"));
    assert.equal(network.requests.length, 1);
  } finally {
    network.restore();
  }
});

test("同一工作区和终端只发送一次相同状态，状态变化和不同键各自发送", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const network = installNetwork([successfulResponse]);
  try {
    await activate(harness.orca);
    await harness.emit(stateEvent("blocked"));
    await harness.emit(stateEvent("blocked"));
    await harness.emit(stateEvent("waiting"));
    await harness.emit(stateEvent("waiting"));
    await harness.emit(stateEvent("blocked", { paneKey: "pane-2" }));
    await harness.emit(stateEvent("blocked", { worktreeId: "D:\\other\\workspace" }));
    await harness.emit(stateEvent("blocked", { worktreeId: null, paneKey: "pane-empty" }));
    await harness.emit(stateEvent("blocked", { worktreeId: null, paneKey: "pane-empty" }));

    assert.equal(network.requests.length, 5);
  } finally {
    network.restore();
  }
});

test("并发重复事件在第一次等待前已经去重", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const originalFetch = globalThis.fetch;
  const originalSetTimeout = globalThis.setTimeout;
  const requests = [];
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    await gate;
    return successfulResponse;
  };
  globalThis.setTimeout = (callback, delay, ...args) => {
    callback(...args);
    return 0;
  };
  try {
    await activate(harness.orca);
    const first = harness.emit(stateEvent("blocked"));
    const second = harness.emit(stateEvent("blocked"));
    release();
    await Promise.all([first, second]);
    assert.equal(requests.length, 1);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.setTimeout = originalSetTimeout;
  }
});

test("网络异常、408、429 和 5xx 按固定间隔重试", async () => {
  const activate = await loadActivate();
  for (const [responses, requestCount, delays] of [
    [
      [
        new Error("token-only-for-tests C:\\private\\workspace private agent output"),
        { ok: false, status: 408 },
        { ok: false, status: 429 },
        successfulResponse,
      ],
      4,
      [1000, 5000, 30000],
    ],
    [[{ ok: false, status: 503 }, successfulResponse], 2, [1000]],
  ]) {
    const harness = createOrca();
    const network = installNetwork(responses);
    try {
      await activate(harness.orca);
      await captureErrors(() => harness.emit(stateEvent("blocked")));
      assert.equal(network.requests.length, requestCount);
      assert.deepEqual(network.delays, delays);
    } finally {
      network.restore();
    }
  }
});

test("其他 4xx 不重试且最终失败仍抑制相同状态", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const network = installNetwork([{ ok: false, status: 401 }]);
  try {
    await activate(harness.orca);
    await captureErrors(async () => {
      await harness.emit(stateEvent("done"));
      await harness.emit(stateEvent("done"));
    });
    assert.equal(network.requests.length, 1);
    assert.deepEqual(network.delays, []);
  } finally {
    network.restore();
  }
});

test("非 5xx 响应不重试", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const network = installNetwork([{ ok: false, status: 600 }]);
  try {
    await activate(harness.orca);
    await captureErrors(() => harness.emit(stateEvent("done")));
    assert.equal(network.requests.length, 1);
    assert.deepEqual(network.delays, []);
  } finally {
    network.restore();
  }
});

test("网络最终失败只输出固定错误且不泄露私密值或事件数据", async () => {
  const activate = await loadActivate();
  const harness = createOrca();
  const network = installNetwork([
    new Error("token-only-for-tests C:\\private\\workspace private agent output"),
  ]);
  try {
    await activate(harness.orca);
    const logs = await captureErrors(async () => {
      await harness.emit(stateEvent("waiting"));
      await harness.emit(stateEvent("waiting"));
    });
    assert.equal(network.requests.length, 4);
    assert.deepEqual(network.delays, [1000, 5000, 30000]);
    assert.equal(logs.length, 1);
    assert.doesNotMatch(logs.join("\n"), /token-only-for-tests/);
    assert.doesNotMatch(logs.join("\n"), /random-topic-7f2c/);
    assert.doesNotMatch(logs.join("\n"), /C:\\private\\workspace/);
    assert.doesNotMatch(logs.join("\n"), /private agent output/);
  } finally {
    network.restore();
  }
});

test("缺少主题时不发送且不读取旧令牌", async () => {
  const activate = await loadActivate();
  const harness = createOrca({ "ntfy-topic": undefined, "ntfy-token": "legacy-token-present" });
  const network = installNetwork([successfulResponse]);
  try {
    await activate(harness.orca);
    const logs = await captureErrors(async () => {
      await harness.emit(stateEvent("blocked"));
    });
    assert.equal(network.requests.length, 0);
    assert.deepEqual(
      harness.secretCalls.map(({ name, args }) => ({ name, key: args.key })),
      [
        { name: "secrets.get", key: "ntfy-topic" },
      ],
    );
    assert.doesNotMatch(logs.join("\n"), /random-topic-7f2c/);
    assert.doesNotMatch(logs.join("\n"), /C:\\private\\workspace/);
    assert.doesNotMatch(logs.join("\n"), /private agent output/);
  } finally {
    network.restore();
  }
});
