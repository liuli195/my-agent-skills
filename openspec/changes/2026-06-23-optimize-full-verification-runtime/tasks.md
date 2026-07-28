## 1. Baseline And Guardrails

- [x] 1.1 Re-run full verification timing and `--durations` evidence before implementation.
- [x] 1.2 Record verify-check and pytest grouped timings for local build contract, PR Flow, Release Flow, Agent Guard, cross-agent-review, Test Framework, and OpenSpec.
- [x] 1.3 Identify the smallest set of true end-to-end tests that must remain process-and-Git based for each user-facing workflow.
- [x] 1.4 Confirm implementation keeps `docs/rules/` out of scope and does not use marker-filtered subsets to satisfy full verification.

## 2. Suite-Wide Repo-Native Test Structure

- [x] 2.1 Add or reuse shared test helpers under `tests/support/` for immutable Git repository templates, command stubs/recorders, and in-process command invocation.
- [x] 2.2 Replace repeated fake CLI process scripts with reusable stubs where command-line process behavior is not under test.
- [x] 2.3 Introduce reusable Git repository fixtures or templates for tests that need equivalent base state.
- [x] 2.4 Keep representative real end-to-end paths for PR Flow, Release Flow, Agent Guard, cross-agent-review, and Test Framework user-facing workflows.
- [x] 2.5 Express test-writing rules in OpenSpec artifacts only; do not create or modify `docs/rules/`.

## 3. PR Flow Runtime Reduction

- [x] 3.1 Reduce complete/tweak grouped runtime from about 77 seconds to 25 seconds or less.
- [x] 3.2 Reduce cleanup plus hotfix grouped runtime from about 60 seconds to 20 seconds or less.
- [x] 3.3 Re-run `tests/test_pr_flow_cli.py` and confirm it is no longer the dominant full-suite bottleneck.
- [x] 3.4 Preserve complete, cleanup, hotfix, tweak, diagnose, review gate, and audit coverage.

## 4. Test Framework Parallel Execution

- [x] 4.1 Add full verification scheduling that runs parallel-safe verify checks concurrently and serial-only checks in the same full verification run.
- [x] 4.2 Add timing output and failure aggregation for every verify check.
- [x] 4.3 Update `.test-framework/config.json` so every verify check has an explicit parallel/serial strategy.
- [x] 4.4 Verify full mode does not use cache hits to skip required checks.

## 5. pytest-xdist Evaluation

- [x] 5.1 Check whether pytest-xdist is already available in the project environment.
- [x] 5.2 If unavailable, record the dependency location and pause for user authorization before any install or command change that requires pytest-xdist.
- [x] 5.3 If available or authorized, evaluate each pytest verify check with pytest-xdist and keep failing or unsafe groups serial.
- [x] 5.4 Document adoption, serial fallback, and no marker-filtered subset evidence in the Design Doc.

## 6. Remaining Suite Bottlenecks

- [x] 6.1 Profile Release Flow, Agent Guard, cross-agent-review, and Test Framework after PR Flow no longer dominates.
- [x] 6.2 Apply the same shared-fixture, stub, and in-process rules to the largest remaining slow group if full verification remains over target; follow-up shared-template and in-process optimizations reduced final uncapped（无限制）full verification to 45.31 seconds after additional regression tests（回归测试）, with a three-run uncapped（无限制）average of 43.64 seconds before that final safety coverage was added.
- [x] 6.3 Keep required end-to-end paths for every optimized workflow.
- [x] 6.4 Trial lower pytest worker（工作进程）counts, `--dist=worksteal`（工作窃取分配）, and a single pytest（Python 测试框架）pool; do not adopt them because measured full verification（完整验证）was slower than the retained config.
- [x] 6.5 Reduce safe remaining overhead by moving Agent Guard（代理守卫）runtime CLI（运行时命令行）tests in-process（进程内） and replacing Test Framework（测试框架）changed-file detection（变更文件检测） with one Git（版本管理）status call.

## 7. Full Suite Target

- [x] 7.1 Run full verification and confirm total runtime is under 60 seconds.
- [x] 7.2 If full verification remains over 60 seconds, profile and optimize the next largest contributor without adding one-off special paths; final retained config uses `maxParallel=0` uncapped（无限制）scheduling and passed at 45.31 seconds.
- [x] 7.3 Write verification report with before/after timings, xdist decision, serial fallback, and remaining risks.
- [x] 7.4 Run `openspec validate optimize-full-verification-runtime --strict --no-interactive` and `openspec validate --all --strict --no-interactive`.

## Verification Report

- target（目标）: full verification（完整验证）under 60 seconds with the canonical command（规范命令） `python plugins/test-framework/skills/test-framework/scripts/test_framework.py verify --project . --full`.
- before（优化前）: baseline evidence（基线证据） recorded `full_verify_seconds=337.57 code=0`; the earlier design estimate was about 214 seconds before the final baseline rerun.
- after（优化后）: final retained full verification（最终保留完整验证） passed with `full_verify_seconds=45.31 code=0`, `maxParallel=0` uncapped（无限制）scheduling, and all configured verify checks（验证检查项） included.
- repeat evidence（重复证据）: three uncapped（无限制）runs reached `43.56s`, `43.28s`, and `44.09s`, average（平均）`43.64s`; three `maxParallel=6` runs averaged `42.28s`.
- final concurrency decision（最终并发决策）: keep `maxParallel=0` even though `maxParallel=6` was about 1.36 seconds faster on this machine, because uncapped（无限制）mode is more compatible across different CPU（处理器）counts and avoids a local-only limit.
- pytest-xdist（并行测试插件）decision（决策）: adopted after user authorization and installation into `C:\Users\liuli\AppData\Local\Programs\Python\Python312\python.exe`; `requirements-dev.txt` records `pytest` and `pytest-xdist` for development setup.
- serial fallback（串行兜底）: Test Framework（测试框架） still supports `parallel: false` checks（检查项）; after xdist（并行测试插件）evaluation, no current pytest（Python 测试框架） verify check（验证检查项） needed serial fallback.
- no subset shortcut（无子集捷径）: final timing used the full configured verify set, not marker-filtered（测试标记过滤） subsets.
- largest remaining contributors（剩余最大耗时来源） from final runner duration（运行器耗时） output: `verify.test-framework seconds=44.70`, `verify.agent-guard seconds=43.38`, and `verify.release-flow seconds=41.78`. These run concurrently, so they identify the highest remaining check-level work but do not add up to wall-clock（墙钟） time.
- retained risk（保留风险）: `maxParallel=0` plus pytest-xdist（并行测试插件） can create high process concurrency on smaller machines; use a local `maxParallel` override if a target environment is resource constrained.
