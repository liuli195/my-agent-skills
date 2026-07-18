---
comet_change: stabilize-version-runtime-sync
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-09-stabilize-version-runtime-sync
status: final
---

# Stabilize Version Runtime Sync Design

## 背景

本变更解决根因 2：测试和流程里曾出现第二份真实版本事实，`build-and-verify`（构建与验证）runtime（运行时）也可能在发布后和目标仓库快照脱节。普通开发和发布中间态允许 manifest（清单）已经提升但 runtime（运行时）尚未刷新，所以普通测试只锁版本来源，不锁中间态一致。

## 方案

仓库内保留现有版本来源模型，不新增版本注册中心。测试只允许从 Codex（编码助手）和 Claude（编码助手）manifest（清单）文件读取真实版本，并断言两者相等。新增版本字面量守卫扫描 `tests/`，拒绝新增真实 `0.1.x` 发布版本硬编码；allowlist（允许列表）只能用于明确夹具，不能覆盖普通断言里的当前真实版本。

Release Flow（发布流程）只在本次发布包含 `build-and-verify`（构建与验证）版本提升时检查 `.build-and-verify/runtime/version.json`。仓库 runtime（运行时）版本和请求发布版本不一致时，preflight（发布预检）返回 `runtime_update_required`（运行时更新要求），输出仓库 runtime（运行时）版本、请求发布版本和 `update-runtime`（更新运行时）命令。该检查只读，不更新 runtime（运行时）、不提交、不推送、不开 PR（拉取请求）。

`build`（构建）和 `verify`（验证）继续只提示 newer user-level runtime（更新的用户级运行时）：输出 runtime（运行时）过期信息和明确 `update-runtime`（更新运行时）命令，不修改 `.build-and-verify/runtime/`。runtime（运行时）过期提示本身不得改变原有退出行为；检查失败仍按原检查失败返回。

用户级 `plugin-sync`（插件同步）路径为 `C:\Users\liuli\.agents\skills\plugin-sync`。只改现有 skill（技能）说明和引用页，不新增仓库内承载位置。`plugin-sync`（插件同步）先做只读检查：没有 `.build-and-verify/config.json` 时输出 `runtime_not_configured`（运行时未配置）；找不到最新已安装 `build-and-verify`（构建与验证）runtime（运行时）时输出 `runtime_source_missing`（运行时来源缺失）；仓库 runtime（运行时）版本等于已安装版本时输出 `runtime_current`（运行时已最新）；仓库版本落后时输出 `runtime_stale`（运行时过期）。`runtime_stale`（运行时过期）必须包含仓库版本、已安装版本和更新命令。只有用户明确授权后才运行现有 `update-runtime`（更新运行时）命令；命令失败输出 `update_failed`（更新失败）；成功后重读 `version.json` 并输出 `runtime_updated`（运行时已更新）。仅当 Git（版本管理）报告 `.build-and-verify/runtime/` 下有 tracked changes（已跟踪变更）时，提示走 PR Flow（拉取请求流程）。不提交、不推送、不开 PR（拉取请求）。

## 边界

- 不新增版本注册中心。
- 不让普通测试强制 manifest（清单）和 runtime（运行时）永远相等。
- 不让 build/verify（构建/验证）自动改仓库文件。
- 不让 plugin-sync（插件同步）扫描全盘。
- 不自动安装、删除、提交、推送或创建 PR（拉取请求）。

## 测试策略

- 仓库测试扫描 `tests/`，拒绝新增真实 `0.1.x` 版本硬编码。
- 双 manifest（清单）测试从 Codex（编码助手）和 Claude（编码助手）manifest（清单）文件读取版本并比较。
- 覆盖 build-and-verify（构建与验证）manifest（清单）和 runtime（运行时）发布中间态不让普通测试失败。
- Release Flow（发布流程）preflight（发布预检）测试覆盖 `runtime_update_required`（运行时更新要求）、版本字段、更新命令和只读不改文件；端到端（端到端）回归从发布入口触发该阻塞。
- build-and-verify（构建与验证）测试覆盖只提示、输出 `update-runtime`（更新运行时）命令、不修改 runtime（运行时）、不因提示本身改变退出行为；端到端（端到端）回归从 build/verify（构建/验证）用户入口执行。
- 用户级 plugin-sync（插件同步）做文档契约和流程检查：状态名统一为 `runtime_not_configured`（运行时未配置）、`runtime_source_missing`（运行时来源缺失）、`runtime_current`（运行时已最新）、`runtime_stale`（运行时过期）、`runtime_updated`（运行时已更新）、`update_failed`（更新失败），并覆盖只读检查、授权更新、更新后重读和 PR Flow（拉取请求流程）提示条件；端到端（端到端）回归覆盖只读检查和授权更新路径，无法实际运行的外部环境部分必须报告无法验证。

## 风险

- 用户级 plugin-sync（插件同步）不在本仓库 Git（版本管理）里，代码验证只能覆盖仓库内契约和文档检查；实际用户级文件需直接检查。
- runtime（运行时）落后不阻塞普通 verify（验证），需要 Release Flow（发布流程）preflight（发布预检）承担发布前阻塞。
- 版本字面量扫描可能误伤测试夹具，因此保留极小 allowlist（允许列表），但不允许真实版本断言进入 allowlist（允许列表）。
