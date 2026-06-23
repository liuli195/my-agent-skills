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
