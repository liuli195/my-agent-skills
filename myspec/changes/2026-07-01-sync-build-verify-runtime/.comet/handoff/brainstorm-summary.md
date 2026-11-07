# Brainstorm Summary

- Change: sync-build-verify-runtime
- Date: 2026-07-01

## 确认的技术方案

采用方案 A：将同一套 `build_and_verify.py` 和 `build_and_verify_runner.py` 复制到 `.build-and-verify/runtime/`，并写入 `version.json`。`init`（初始化）首次复制，`update-runtime`（更新运行时）显式刷新当前正在执行的 runtime（运行时）；`build/verify`（构建/验证）只做版本落后提示，不自动修改文件。

## 关键取舍与风险

- 只复制 runtime（运行时），不复制完整 Plugin（插件）。
- 版本发现使用标准库在用户级 Codex（代码助手）和 Claude（Claude 版本）常见 Plugin（插件）位置 best-effort（尽力而为）查找，不引入依赖或配置。
- 仓库内旧 runtime（运行时）发现用户级新版时，提示必须给出新版脚本路径，避免旧脚本只刷新自己。
- 风险：用户级 runtime（运行时）不可发现时无法提示；处理方式是静默继续，保持 CI（持续集成）稳定。

## 测试策略

用现有 `tests/test_build_and_verify_plugin.py` 覆盖初始化复制、显式更新、版本提示、不自动更新、Skill（技能）文案和 spec（规格）契约。另做端到端（端到端）回归：临时目标仓库从 `init`（初始化）到仓库 runtime（运行时）执行 `update-runtime`、`build` 和 `verify`（更新运行时、构建、验证）。

## Spec Patch

无新增候选；当前 delta spec（增量规格）已覆盖 init（初始化）、update-runtime（更新运行时）、版本提示和仓库固定入口。
