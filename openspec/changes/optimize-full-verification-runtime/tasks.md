## 1. Baseline And Guardrails

- [ ] 1.1 Re-run full verification timing and `--durations` evidence before implementation.
- [ ] 1.2 Record PR Flow grouped timings for complete/tweak, cleanup, hotfix, diagnose.
- [ ] 1.3 Identify the smallest set of true end-to-end PR Flow tests that must remain process-and-Git based.

## 2. PR Flow Test Structure

- [ ] 2.1 Add or reuse a fast in-process PR Flow invocation helper for tests that do not need Python process startup.
- [ ] 2.2 Replace repeated fake `gh` process scripts with in-process stubs where command-line process behavior is not under test.
- [ ] 2.3 Introduce a reusable Git repository fixture or template for tests that need equivalent base state.
- [ ] 2.4 Keep at least one complete lifecycle, one cleanup, and one hotfix path on real Git state.

## 3. Runtime Reduction

- [ ] 3.1 Reduce complete/tweak grouped runtime from about 77 seconds to 25 seconds or less.
- [ ] 3.2 Reduce cleanup plus hotfix grouped runtime from about 60 seconds to 20 seconds or less.
- [ ] 3.3 Re-run `tests/test_pr_flow_cli.py` and confirm it is no longer the dominant full-suite bottleneck.

## 4. Full Suite Target

- [ ] 4.1 Run full verification and confirm total runtime is under 60 seconds.
- [ ] 4.2 If full verification remains over 60 seconds, profile and optimize the next largest contributor.
- [ ] 4.3 Write verification report with before/after timings and remaining risks.
