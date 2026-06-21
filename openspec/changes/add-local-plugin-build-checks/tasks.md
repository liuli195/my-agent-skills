## 1. Test Coverage

- [x] 1.1 Add tests for `scripts/check.py build` covering Claude validation command discovery, marketplace source validation, manifest name matching, Codex manifest path checks, projection registration consistency, and Guard Profile（守卫画像）template mirror checks.
- [x] 1.2 Add tests for `scripts/check.py verify` proving it delegates to `python -m pytest` and uses repository pytest（Python 测试框架）configuration.
- [x] 1.3 Add tests for `.comet/config.yaml` requiring `build_command: python scripts/check.py build` and `verify_command: python scripts/check.py verify`.

## 2. Build And Verify Commands

- [x] 2.1 Add `scripts/check.py` with `build` and `verify` subcommands.
- [x] 2.2 Implement Claude（Claude 编码工具）plugin validation for the repository marketplace and every local plugin source.
- [x] 2.3 Implement local marketplace and plugin manifest consistency checks for Claude and Codex（OpenAI 编码代理）surfaces.
- [x] 2.4 Implement release-flow projection（发布流程投影）plugin registration consistency checks.
- [x] 2.5 Implement Guard Profile template mirror consistency checks.
- [x] 2.6 Add standard pytest configuration in `pyproject.toml`.

## 3. Comet Integration

- [x] 3.1 Update `.comet/config.yaml` to use the new build and verify commands.
- [x] 3.2 Remove or retire `.comet/build-check.sh` after confirming it is no longer referenced.

## 4. Verification

- [x] 4.1 Run focused tests for the new command behavior.
- [x] 4.2 Run `python scripts/check.py build`.
- [x] 4.3 Run `python scripts/check.py verify`.
- [x] 4.4 Confirm no Comet（双星流程）source files or installed Comet scripts were modified.

## 5. Agent Guard Hotfix

- [x] 5.1 Reproduce the Global Command Guard（全局命令守卫）miss through direct hook（直接钩子）and standard event bridge（标准事件桥接）inputs.
- [x] 5.2 Preserve top-level `command` fields when adapting PreToolUse（工具使用前）payloads.
- [x] 5.3 Add regression tests for both `hook_router.py` and `run_guard_event.py` command-field paths.
- [x] 5.4 Re-run Agent Guard runtime（运行时）tests and full repository verify（验证）.

## 6. Cross-Agent Review Hotfix

- [x] 6.1 Reproduce `Reviewer returned invalid findings` from structured reviewer output.
- [x] 6.2 Normalize dict-shaped reviewer `findings` with `issues` or `gaps` without creating false CRITICAL（严重）findings.
- [x] 6.3 Add regression tests for pass dict findings and gap dict findings.
- [x] 6.4 Re-run cross-agent-review（跨代理审查）tests and full repository verify（验证）.

## 7. Agent Guard Hook Blocking Hotfix

- [x] 7.1 Reproduce that Global Command Guard（全局命令守卫）writes deny audit（拒绝审计） but the host still executes the Comet build transition.
- [x] 7.2 Align stdin hook（标准输入钩子） deny/ask results with the host block exit code `2`.
- [x] 7.3 Keep `--payload-file` debug semantics unchanged for runtime tests and standard event bridge（标准事件桥接） calls.
- [x] 7.4 Add regression coverage for stdin hook blocking and re-run Agent Guard runtime（运行时） tests.
