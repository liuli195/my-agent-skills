# 01 — 新增跨平台 Full Verify（完整验证）汇总门禁

**What to build:** 让拉取请求的唯一必需 `Full Verify` 检查代表 Linux 和 Windows 平台验证的共同结果；只有所有平台任务成功时才通过，任一平台失败、取消或跳过时阻止合并。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [x] Linux 和 Windows 平台验证任务继续独立并行运行。
- [x] 新的 `Full Verify` 汇总任务等待两个平台任务，并严格要求两个结果均为 `success`。
- [x] 现有 `.pr-flow/config.yaml` 和 GitHub Ruleset（规则集）继续使用 `Full Verify` 作为唯一必需检查。
- [x] 本地工作流契约检查先失败后通过，覆盖汇总任务依赖和失败结果处理。
- [ ] 真实拉取请求成功路径确认 `Full Verify` 指向汇总任务。
- [ ] 受控平台失败路径确认 `Full Verify` 失败或保持阻塞。

## Behavior Evidence

- Red：实现前运行 `python -m pytest -q -p no:cacheprovider tests/test_build_and_verify_cli.py -k full_verify_is_the_cross_platform_required_gate`，因缺少 `full-verify-gate` 失败。
- Green：新增汇总任务后同一检查通过（1 passed）。
- Targeted checks：`python -m pytest -q -p no:cacheprovider tests/test_build_and_verify_cli.py tests/test_setup_worktree_script.py`，22 passed。
- Fast verification：`build-and-verify verify --project .`，通过；运行 2 项受影响检查。
- User-entry smoke：待 PR CI（拉取请求持续集成）运行后确认真实必需检查指向汇总任务。
- Review：Standards（规范）与 Spec（规格）审查及修复跟进均无阻断发现；保留两项待真实 PR CI 验证。
- Known risk：本地无法模拟 GitHub Actions（GitHub 工作流）任务结果组合；失败路径需由真实 PR CI 或等价受控运行确认。
