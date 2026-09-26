#!/usr/bin/env node

const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");

const candidates = process.env.BUILD_AND_VERIFY_PYTHON ? [[process.env.BUILD_AND_VERIFY_PYTHON, []]] : [];
candidates.push(["python3.12", []], ["python3", []], ["python", []]);
if (process.platform === "win32") candidates.push(["py", ["-3.12"]]);

const selected = candidates.find(([command, prefix]) => {
  const probe = spawnSync(command, [...prefix, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], { encoding: "utf8", windowsHide: true });
  return probe.status === 0 && /^3\.(?:1[2-9]|[2-9]\d)$/.test(probe.stdout.trim());
});
if (!selected) {
  console.error("error: Python 3.12 or newer is required");
  process.exit(1);
}

const [python, prefix] = selected;
const args = process.argv.slice(2);
const lifecycle = ["doctor", "update"].includes(args[0]) || (args[0] === "init" && args.some((arg) => ["--pi", "--claude", "--codex", "--all", "--dev", "--release"].includes(arg)));
const core = path.join(__dirname, "..", "python", lifecycle ? "management_cli.py" : "build_and_verify.py");
const child = spawn(python, [...prefix, core, ...args], { stdio: "inherit", windowsHide: true });
child.on("error", (error) => {
  console.error(`error: cannot start Python: ${error.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 1)));
