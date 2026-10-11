#!/usr/bin/env node

const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");

const candidates = [];
if (process.env.MYSPEC_PYTHON) {
  candidates.push([process.env.MYSPEC_PYTHON, []]);
}
candidates.push(["python3.12", []], ["python3", []], ["python", []]);
if (process.platform === "win32") {
  candidates.push(["py", ["-3.12"]]);
}

let selected;
const checked = [];
for (const [command, prefix] of candidates) {
  const probe = spawnSync(
    command,
    [...prefix, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
    { encoding: "utf8", windowsHide: true },
  );
  const version = probe.status === 0 ? probe.stdout.trim() : "unavailable";
  checked.push(`${command}${prefix.length ? ` ${prefix.join(" ")}` : ""} (${version})`);
  const match = /^(\d+)\.(\d+)$/.exec(version);
  if (match && (Number(match[1]) > 3 || (Number(match[1]) === 3 && Number(match[2]) >= 12))) {
    selected = [command, prefix];
    break;
  }
}

if (!selected) {
  console.error(`error: Python 3.12 or newer is required; checked ${checked.join(", ")}`);
  process.exit(1);
}

const [python, prefix] = selected;
const core = path.join(__dirname, "..", "python", "spec_ops.py");
const child = spawn(python, [...prefix, core, ...process.argv.slice(2)], {
  stdio: "inherit",
  windowsHide: true,
});
const signalHandlers = new Map(
  ["SIGINT", "SIGTERM"].map((signal) => [signal, () => child.kill(signal)]),
);
for (const [signal, handler] of signalHandlers) {
  process.on(signal, handler);
}
child.on("error", (error) => {
  console.error(`error: cannot start Python: ${error.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => {
  for (const [forwardedSignal, handler] of signalHandlers) {
    process.off(forwardedSignal, handler);
  }
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 1);
  }
});
