---
comet_change: sync-build-verify-runtime
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-01-sync-build-verify-runtime
status: final
---

# Sync Build And Verify Runtime Design

## 背景

`build-and-verify`（构建与验证）runtime（运行时）当前随 Plugin（插件）安装在用户级 cache（缓存）目录。该路径不适合作为仓库文档和 CI（持续集成）的长期命令入口，因为 Plugin（插件）更新后路径可能变化，CI（持续集成）也没有用户级 runtime（运行时）。

本次采用方案 A：只复制 runtime（运行时）快照，不复制完整 Plugin（插件）。

## 目标

- 仓库固定入口为 `.build-and-verify/runtime/build_and_verify.py`。
- 用户级和仓库内 runtime（运行时）使用同一份代码能力。
- `init`（初始化）首次复制 runtime（运行时）快照。
- `update-runtime`（更新运行时）显式刷新 runtime（运行时）快照。
- `build/verify`（构建/验证）只提示版本落后，不自动修改文件。

## 非目标

- 不实现项目级 Plugin（插件）安装器。
- 不复制完整 Plugin（插件）目录。
- 不引入新依赖。
- 不修改用户级 Codex（代码助手）配置。
- 不在 `build/verify`（构建/验证）里自动更新 runtime（运行时）。

## 运行时布局

仓库内 runtime（运行时）目录：

```text
.build-and-verify/runtime/
  build_and_verify.py
  build_and_verify_runner.py
  version.json
```

`version.json` 记录当前复制来源的 Plugin（插件）版本和 runtime（运行时）版本元数据。它只用于提示和审计，不作为运行前强校验。

## 命令行为

`build_and_verify.py` 支持同一组命令：

```text
init
update-runtime
build
verify
```

`init --project <repo>`：

- 创建 `.build-and-verify/config.json`。
- 创建 `.build-and-verify/.gitignore`。
- 创建 `.build-and-verify/cache/`。
- 复制当前 runtime（运行时）到 `.build-and-verify/runtime/`。
- 如果配置文件、忽略文件或 runtime（运行时）目录已存在，则先拒绝写入并报告冲突路径。

`update-runtime --project <repo>`：

- 刷新 `.build-and-verify/runtime/`。
- 复制来源固定为当前正在执行的 runtime（运行时）目录。
- 只复制 runtime（运行时）文件和版本元数据。
- 不改 `.build-and-verify/config.json`。
- 不从隐式用户级路径自动选择其他复制来源。

`build/verify --project <repo>`：

- 运行前尽力查找可发现的用户级 runtime（运行时）版本。
- 如果用户级版本领先仓库版本，输出 `runtime_outdated`（运行时过期）提示和使用新版脚本执行 `update-runtime`（更新运行时）的命令。
- 如果找不到用户级 runtime（运行时），静默继续。
- 永不自动修改 `.build-and-verify/runtime/`。

## 版本发现

版本发现使用 Python（Python 语言）标准库，避免新增依赖。优先从当前 runtime（运行时）附近读取 `version.json`。仓库 runtime（运行时）查找用户级版本时，只做 best-effort（尽力而为）搜索：

- Windows（Windows 系统）默认检查 `%USERPROFILE%\.codex\plugins\cache`。
- Windows（Windows 系统）也检查 Claude（Claude 版本）常见用户级 Plugin（插件）目录。
- 找不到、读不到、格式不匹配时静默跳过。

版本提示不能影响 `build/verify`（构建/验证）的退出码。

## 测试策略

使用现有 `tests/test_build_and_verify_plugin.py` 覆盖：

- `init`（初始化）复制 runtime（运行时）快照。
- `init`（初始化）遇到已有 runtime（运行时）目录时拒绝静默覆盖。
- `update-runtime`（更新运行时）刷新 runtime（运行时）快照但不改配置。
- `build/verify`（构建/验证）发现用户级版本领先时只提示，不修改 runtime（运行时）。
- `build/verify`（构建/验证）找不到用户级版本时继续运行。
- Skill（技能）文案和 OpenSpec（开放规格）契约不再要求“不复制 runner（运行器）”。
- 端到端（端到端）回归从用户入口运行：在临时目标仓库执行 `init`（初始化），再用 `.build-and-verify/runtime/build_and_verify.py` 执行 `update-runtime`、`build` 和 `verify`（更新运行时、构建、验证），并确认 `build/verify`（构建/验证）不修改 runtime（运行时）。

## 风险

- 用户级 runtime（运行时）不可发现时不会提示版本落后；这是可接受的，因为 CI（持续集成）稳定性优先。
- 仓库会新增少量 runtime（运行时）文件；这是固定命令入口的直接成本。
- 用户可能忘记提交更新后的 runtime（运行时）；通过 `runtime_outdated`（运行时过期）提示降低概率。
