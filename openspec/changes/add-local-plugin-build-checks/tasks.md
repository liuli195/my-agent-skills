## 1. Test Coverage

- [ ] 1.1 Add tests for `scripts/check.py build` covering Claude validation command discovery, marketplace source validation, manifest name matching, Codex manifest path checks, projection registration consistency, and Guard Profile（守卫画像）template mirror checks.
- [ ] 1.2 Add tests for `scripts/check.py verify` proving it delegates to `python -m pytest` and uses repository pytest（Python 测试框架）configuration.
- [ ] 1.3 Add tests for `.comet/config.yaml` requiring `build_command: python scripts/check.py build` and `verify_command: python scripts/check.py verify`.

## 2. Build And Verify Commands

- [ ] 2.1 Add `scripts/check.py` with `build` and `verify` subcommands.
- [ ] 2.2 Implement Claude（Claude 编码工具）plugin validation for the repository marketplace and every local plugin source.
- [ ] 2.3 Implement local marketplace and plugin manifest consistency checks for Claude and Codex（OpenAI 编码代理）surfaces.
- [ ] 2.4 Implement release-flow projection（发布流程投影）plugin registration consistency checks.
- [ ] 2.5 Implement Guard Profile template mirror consistency checks.
- [ ] 2.6 Add standard pytest configuration in `pyproject.toml`.

## 3. Comet Integration

- [ ] 3.1 Update `.comet/config.yaml` to use the new build and verify commands.
- [ ] 3.2 Remove or retire `.comet/build-check.sh` after confirming it is no longer referenced.

## 4. Verification

- [ ] 4.1 Run focused tests for the new command behavior.
- [ ] 4.2 Run `python scripts/check.py build`.
- [ ] 4.3 Run `python scripts/check.py verify`.
- [ ] 4.4 Confirm no Comet（双星流程）source files or installed Comet scripts were modified.
