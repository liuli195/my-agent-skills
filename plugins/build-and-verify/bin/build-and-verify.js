#!/usr/bin/env node

const { spawn, spawnSync } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const startedAt = process.hrtime.bigint();
const args = process.argv.slice(2);
const elapsed = () => Number(process.hrtime.bigint() - startedAt) / 1e9;
const argument = (name) => {
  let value;
  for (let index = 0; index < args.length; index++) {
    if (args[index] === name) value = args[index + 1];
    else if (args[index].startsWith(`${name}=`)) value = args[index].slice(name.length + 1);
  }
  return value;
};
const project = path.resolve(argument("--project") || ".");
const context = argument("--execution-context") || process.env.BUILD_AND_VERIFY_EXECUTION_CONTEXT;
const localBudgetCandidate = args[0] === "verify" && context === "local" && !args.includes("--pr") && !args.includes("--diagnostic")
  && process.env.GITHUB_ACTIONS !== "true" && process.env.CI?.toLowerCase() !== "true";
let verify;
if (localBudgetCandidate) {
  try { verify = JSON.parse(fs.readFileSync(path.join(project, ".build-and-verify/config.json"), "utf8")).verify; } catch {}
}
const budget = localBudgetCandidate && (verify?.enforceLocalBudget === undefined || verify.enforceLocalBudget === true)
  && Number.isInteger(verify?.fullBudgetSeconds) && verify.fullBudgetSeconds > 0 ? verify.fullBudgetSeconds : null;
let timeoutReported = false;
let selectedIds = Array.isArray(verify?.checks) ? verify.checks.map((check) => check.id) : [];
const observedChecks = new Map();
let runtimePhase = "startup";
let runtimeVersion = "unknown";
const startupTimeout = (phase = "startup") => {
  if (timeoutReported) return;
  timeoutReported = true;
  const checks = selectedIds.map((id) => ({ id, ...(observedChecks.get(id) || { status: "not_started", durationSeconds: 0 }) }));
  for (const check of checks) {
    if (check.status === "running") check.status = "timed_out";
    if (["timed_out", "not_started"].includes(check.status)) check.reason = "total_budget_timeout";
  }
  const failure = { schemaVersion: 1, runtimeVersion, generatedAt: new Date().toISOString(),
    totalSeconds: elapsed(), budgetSeconds: budget, overBudget: true, verificationStatus: "failed",
    executionContext: "local", diagnostic: false, reason: "total_budget_timeout", phase, checks,
    unfinished: checks.filter((check) => check.status === "timed_out").map((check) => check.id),
    notStarted: checks.filter((check) => check.status === "not_started").map((check) => check.id) };
  console.error(`total_budget_timeout: totalSeconds=${failure.totalSeconds.toFixed(2)} budgetSeconds=${budget}; phase=${phase}${phase === "startup" ? "" : "; bounded-cleanup-fallback"}`);
  if (phase === "migration") console.error("legacy_runtime_migration_interrupted: inspect staged changes; no automatic rollback");
  console.error(`unfinished: ${failure.unfinished.join(", ")}`);
  console.error(`not-started: ${failure.notStarted.join(", ")}`);
  console.error("status: failed");
  // Owned processes have already stopped. Reporting is best effort and bounded;
  // a blocked filesystem must not keep the public entry alive indefinitely.
  const finish = (error) => {
    if (error) console.error("performance-report-warning: cannot finalize timeout report");
    process.exit(1);
  };
  setTimeout(() => finish(true), 100);
  const reportPath = path.join(project, ".build-and-verify/runs/performance-report.json");
  fs.mkdir(path.dirname(reportPath), { recursive: true }, (mkdirError) => {
    if (mkdirError) return finish(mkdirError);
    const temporary = `${reportPath}.startup.tmp`;
    fs.writeFile(temporary, JSON.stringify(failure, null, 2) + "\n", (writeError) => {
      if (writeError) return finish(writeError);
      fs.rename(temporary, reportPath, finish);
    });
  });
};

(async () => {
const runtimePath = path.join(__dirname, "..", "python", "build_and_verify_runner.py");
const bootstrapCode = "import importlib.util,sys; spec=importlib.util.spec_from_file_location('build_and_verify_bootstrap_runner',sys.argv[1]); module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module); module._bootstrap_cli()";
let ownedProcess;
let startupGuard;
const stopOwned = () => {
  if (!ownedProcess?.pid) return;
  if (process.platform === "win32" && ownedProcess.exitCode !== null) return;
  if (process.platform === "win32") {
    // The -S bootstrap installs the owning job before any site initialization.
    // Terminating the bootstrap closes its job and its descendants.
    ownedProcess.kill();
  } else {
    try { process.kill(-ownedProcess.pid, "SIGKILL"); } catch (error) { if (error.code !== "ESRCH") throw error; }
  }
};
if (budget !== null) {
  startupGuard = setTimeout(() => { stopOwned(); startupTimeout(); }, Math.max(0, (budget - elapsed()) * 1000));
}
const candidates = process.env.BUILD_AND_VERIFY_PYTHON ? [[process.env.BUILD_AND_VERIFY_PYTHON, []]] : [];
candidates.push(["python3.12", []], ["python3", []], ["python", []]);
if (process.platform === "win32") candidates.push(["py", ["-3.12"]]);

let pythonStartedAt;
let selected;
for (const [command, prefix] of candidates) {
  if (budget !== null && elapsed() >= budget) break;
  const probeArgs = budget === null
    ? [...prefix, "-c", "import sys,time; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(time.monotonic())"]
    : [...prefix, "-S", "-c", bootstrapCode, runtimePath, "--probe"];
  const probe = budget === null ? spawnSync(command, probeArgs, { encoding: "utf8", windowsHide: true })
    : await new Promise((resolve) => {
      const processProbe = spawn(command, probeArgs, { windowsHide: true,
        detached: process.platform !== "win32", stdio: ["ignore", "pipe", "ignore"] });
      ownedProcess = processProbe;
      let stdout = "";
      processProbe.stdout.setEncoding("utf8");
      processProbe.stdout.on("data", (data) => { stdout += data; });
      processProbe.on("error", () => resolve({ status: null, stdout }));
      processProbe.on("close", (status) => resolve({ status, stdout }));
    });
  const [version, clock] = (probe.stdout || "").trim().split(/\r?\n/);
  if (probe.status !== 0 || !/^3\.(?:1[2-9]|[2-9]\d)$/.test(version)) continue;
  // Calibrate against the actual Python monotonic clock. Probe transit is
  // conservatively charged too; do not assume cross-runtime clock epochs.
  pythonStartedAt = Number(clock) - elapsed();
  if (Number.isFinite(pythonStartedAt)) { selected = [command, prefix]; break; }
}
if (budget !== null && elapsed() >= budget) {
  startupTimeout();
  return;
}
if (!selected) {
  console.error("error: Python 3.12 or newer is required");
  process.exit(1);
}

const [python, prefix] = selected;
const lifecycle = ["doctor", "update"].includes(args[0]) || (args[0] === "init" && args.some((arg) => ["--claude", "--codex", "--all", "--dev", "--release"].includes(arg)));
const core = path.join(__dirname, "..", "python", lifecycle ? "management_cli.py" : "build_and_verify.py");
const childArgs = budget === null ? [...prefix, core, ...args] : [...prefix, "-S", "-c", bootstrapCode, runtimePath, core, ...args];
const child = spawn(python, childArgs, {
  stdio: budget === null ? "inherit" : ["inherit", "pipe", "inherit"], windowsHide: true,
  detached: budget !== null && process.platform !== "win32",
  env: { ...process.env, BUILD_AND_VERIFY_STARTED_MONOTONIC: String(pythonStartedAt),
    ...(budget === null ? {} : { BUILD_AND_VERIFY_STARTUP_GUARD: "1" }) },
});
ownedProcess = child;
let formalSuccess;
let finalReport;
if (budget !== null) {
  // This watchdog owns only startup. Python acknowledges after its owning job
  // and the same deadline's watchdog are installed, then this timer is retired.
  let pending = "";
  child.stdout.setEncoding("utf8");
  child.stdout.on("data", (data) => {
    pending += data;
    let newline;
    while ((newline = pending.indexOf("\n")) >= 0) {
      const line = pending.slice(0, newline + 1);
      pending = pending.slice(newline + 1);
      let result, plan;
      if (line.trim().startsWith("build-and-verify-formal-result:")) {
        try { result = JSON.parse(line.trim().slice("build-and-verify-formal-result:".length)); } catch {}
      } else if (line.trim().startsWith("build-and-verify-selected:")) {
        try { plan = JSON.parse(line.trim().slice("build-and-verify-selected:".length)); } catch {}
      }
      if (result && ["passed", "skipped", "failed"].includes(result.status)
          && Number.isInteger(result.code) && result.code >= 0
          && (result.report === null || (typeof result.report === "object" && !Array.isArray(result.report)))) {
        formalSuccess = result.code === 0 ? result.status : undefined;
        finalReport = result.report;
        // Preserve this invocation's failure reasons if final report I/O
        // crosses the same deadline and the bounded fallback takes over.
        if (Array.isArray(finalReport?.checks)) {
          for (const check of finalReport.checks) {
            if (check && typeof check.id === "string") observedChecks.set(check.id, { ...check });
          }
        }
        runtimePhase = "finalization";
        startupGuard = setTimeout(() => { stopOwned(); startupTimeout(runtimePhase); }, Math.max(0, (budget - elapsed()) * 1000));
      } else if (line.trim().startsWith("build-and-verify-phase:")) {
        runtimePhase = line.trim().split(":")[1];
      } else if (plan && Array.isArray(plan.ids) && plan.ids.every((id) => typeof id === "string")
          && typeof plan.runtimeVersion === "string") {
        selectedIds = plan.ids;
        runtimeVersion = plan.runtimeVersion;
        runtimePhase = "checks";
      } else if (line.trim() === "build-and-verify-startup-guard-ready") {
        clearTimeout(startupGuard);
        startupGuard = null;
        runtimePhase = "preparation";
      } else {
        if (line.startsWith("check-start: ")) observedChecks.set(line.trim().slice(13), { status: "running", durationSeconds: 0 });
        if (line.startsWith("cache-hit: ")) observedChecks.set(line.trim().slice(11), { status: "cached", durationSeconds: 0 });
        const ended = /^check-end: (.+) status=(\S+) seconds=(\S+)/.exec(line);
        if (ended) observedChecks.set(ended[1], { status: ended[2], durationSeconds: Number(ended[3]) });
        process.stdout.write(line);
      }
    }
  });
  child.stdout.on("end", () => { if (pending) process.stdout.write(pending); });
}
child.on("error", (error) => {
  console.error(`error: cannot start Python: ${error.message}`);
  process.exit(1);
});
child.on("close", (code, signal) => {
  if (startupGuard) clearTimeout(startupGuard);
  if (timeoutReported) return;
  // POSIX cutoff kills its owning process group, so Node observes SIGKILL
  // instead of Python's exit 124. Keep the original deadline for reporting.
  if (budget !== null && signal === "SIGKILL" && runtimePhase !== "startup") {
    startupGuard = setTimeout(() => startupTimeout(runtimePhase), Math.max(0, (budget - elapsed()) * 1000));
    return;
  }
  if (budget !== null && (code === 124 || elapsed() >= budget)) {
    startupTimeout(runtimePhase);
    return;
  }
  const finish = () => {
    if (timeoutReported) return;
    if (budget !== null && elapsed() >= budget) { startupTimeout("finalization"); return; }
    if (startupGuard) clearTimeout(startupGuard);
    if (code === 0 && formalSuccess) console.log(`status: ${formalSuccess}`);
    process.exit(signal ? 1 : (code ?? 1));
  };
  if (!finalReport) return finish();
  // The public entry owns final report I/O after the interpreter exits, using
  // only the original deadline's remaining time. No success is emitted early.
  startupGuard = setTimeout(() => startupTimeout("finalization"), Math.max(0, (budget - elapsed()) * 1000));
  const reportPath = path.join(project, ".build-and-verify/runs/performance-report.json");
    finalReport.totalSeconds = elapsed();
    finalReport.verificationStatus = code === 0 ? formalSuccess || "passed" : "failed";
    const temporary = `${reportPath}.entry.tmp`;
    fs.writeFile(temporary, JSON.stringify(finalReport, null, 2) + "\n", (writeError) => {
      if (timeoutReported) return;
      if (writeError) { console.error("performance-report-warning: cannot finalize report"); return finish(); }
      if (elapsed() >= budget) { startupTimeout("finalization"); return; }
      fs.rename(temporary, reportPath, (renameError) => {
        if (renameError) console.error("performance-report-warning: cannot finalize report");
        finish();
      });
    });
});
})().catch((error) => { console.error(`error: ${error.message}`); process.exit(1); });
