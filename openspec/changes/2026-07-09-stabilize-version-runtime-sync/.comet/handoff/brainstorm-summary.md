# Brainstorm Summary

- Change: stabilize-version-runtime-sync
- Date: 2026-07-09

## 已确认事实

- OpenSpec（规格流程）已定义四块范围：版本字面量守卫、Release Flow（发布流程）预检、build-and-verify（构建与验证）只提示不改文件、plugin-sync（插件同步）运行时闭环。
- 本仓库已有 build-and-verify（构建与验证）运行时提示和 `update-runtime`（更新运行时）命令。
- 本仓库已有 Release Flow（发布流程）`preflight_errors`（预检错误）入口，可在这里增加 `runtime_update_required`（运行时更新要求）。
- 本仓库没有 plugin-sync（插件同步）实现文件；用户已授权修改用户级路径 `C:\Users\liuli\.agents\skills\plugin-sync`。
- `plugin-sync`（插件同步）已有 `references/update-build-and-verify-runtime.md`，可在现有说明里补齐 `runtime_current` / `runtime_stale`（运行时已最新/运行时过期）检查和授权更新闭环。
- 目标是解决根因 2：锁住版本事实来源，并补齐 build-and-verify（构建与验证）runtime（运行时）同步闭环。

## 确认的技术方案

- 仓库内实现五块：测试禁止新增真实 `0.1.x` 硬编码、Codex（编码助手）和 Claude（编码助手）manifest（清单）版本一致性检查、runtime（运行时）和 manifest（清单）发布中间态不让普通测试失败、Release Flow（发布流程）runtime（运行时）预检、build-and-verify（构建与验证）报告不变性测试。
- 用户级 `plugin-sync`（插件同步）只改现有 skill（技能）说明和引用页，不新增仓库内承载位置。
- `plugin-sync`（插件同步）检查默认只读：只读检查 `.build-and-verify/config.json`、仓库 runtime（运行时）版本、已安装 runtime（运行时）版本，输出 `runtime_not_configured` / `runtime_source_missing` / `runtime_current` / `runtime_stale`（运行时未配置/运行时来源缺失/运行时已最新/运行时过期）和更新命令。
- `plugin-sync`（插件同步）只有用户授权时才运行 build-and-verify（构建与验证）现有 `update-runtime`（更新运行时）命令；失败输出 `update_failed`（更新失败），成功后重读 `version.json` 并输出 `runtime_updated`（运行时已更新），仅当 Git（版本管理）报告 `.build-and-verify/runtime/` 有 tracked changes（已跟踪变更）时提示走 PR Flow（拉取请求流程）。

## 关键取舍与风险

- 最小实现不新增版本注册中心，版本事实继续来自 manifest（清单）和 runtime（运行时）文件。
- 普通 verify（验证）不阻塞 stale runtime（过期运行时），发布前由 Release Flow（发布流程）阻塞。
- 用户级 `plugin-sync`（插件同步）不在本仓库 Git（版本管理）里，验证只能通过文件检查和引用页契约检查覆盖。

## 测试策略

- 加一个仓库测试扫描 `tests/` 中新增真实 `0.1.x` 版本字面量，只允许明确白名单。
- 保留/补强双 manifest（清单）文件读取和相等检查，禁止用硬编码真实版本替代。
- 加普通测试不因 build-and-verify（构建与验证）runtime（运行时）和 manifest（清单）发布中间态不一致而失败的覆盖。
- 加 Release Flow（发布流程）预检测试覆盖 `runtime_update_required`（运行时更新要求）、版本字段、更新命令和只读不改文件。
- 保留/补强 build-and-verify（构建与验证）运行时落后时只提示、输出 `update-runtime`（更新运行时）命令、不改文件、不因提示本身改变退出行为的测试。
- 对用户级 plugin-sync（插件同步）文档做契约检查：状态名统一、只读检查和授权更新分段、更新后重读和 PR Flow（拉取请求流程）提示条件齐全。
- 增加端到端（端到端）回归：Release Flow（发布流程）preflight（发布预检）发布入口、build/verify（构建/验证）用户入口、plugin-sync（插件同步）只读检查和授权更新路径。

## Spec Patch

- 无。
