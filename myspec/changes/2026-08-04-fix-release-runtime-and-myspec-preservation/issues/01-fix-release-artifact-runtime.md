# 01 — 修复 Release Workflow（发布工作流）候选包上传动作运行时

**关联问题：** #123

**What to build（构建内容）：** 让当前发布工作流和发布工作流模板使用首个 Node.js 24（运行时）候选包上传动作，并通过工作流契约检查阻止旧 Node.js 20（运行时）动作重新出现。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** completed

- [x] 当前发布工作流和发布工作流模板的候选包上传动作均使用 `@v6`。
- [x] 工作流契约检查拒绝该动作的 `@v4`、`@v5` 版本，并保留现有候选包上传与发布顺序。
- [x] 公开发布工作流配置检查通过，未改变触发器、权限和发布输出语义。
- [x] Build and Verify（构建与验证）快速检查通过。

## Behavior evidence（行为证据）

- 红灯依据：基线工作流仍为 `actions/upload-artifact@v4`；新增 `@v6` 契约断言在该基线上失败。
- 绿灯：`python -m pytest -q -p no:cacheprovider tests/test_release_flow_cli.py -k "release_workflows_publish_only_verified_selected_npm_packages or workflows_use_current_low_risk_action_versions"`，2 项通过。
- 快速验证：`build-and-verify verify --project .`，`verify.local-build-contract`、`verify.release-flow`、`verify.runtime-boundaries` 和 `verify.build-and-verify` 均缓存命中并通过。
- 保持不变：发布工作流触发器、权限、候选包上传顺序和发布输出未修改。
