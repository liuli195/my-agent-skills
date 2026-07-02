## Context

本仓库有两类版本漂移风险：测试或代码写第二份真实插件版本，以及 build-and-verify（构建与验证）runtime（运行时）快照在发布后落后。普通开发和发布中间态允许 manifest（清单）已经提升但 runtime（运行时）尚未刷新，所以不能用普通测试强制二者永远一致。

## Goals / Non-Goals

**Goals:**

- 锁住版本事实来源，避免新增真实 `0.1.x` 硬编码。
- 保留 Codex（编码助手）和 Claude（编码助手）manifest（清单）一致性检查。
- 在 Release Flow（发布流程）发布前拦截 build-and-verify（构建与验证）runtime（运行时）未同步。
- 让 plugin-sync（插件同步）负责目标仓库 runtime（运行时）同步闭环。

**Non-Goals:**

- 不新增版本注册中心。
- 不让普通测试强制 runtime（运行时）永远等于 manifest（清单）。
- 不让 build/verify（构建/验证）自动修改 runtime（运行时）。
- 不自动提交或推送 runtime（运行时）更新。

## Decisions

1. 普通测试只锁来源，不锁中间态一致。

   仓库测试禁止真实版本常量，继续检查双 manifest（清单）相等。runtime（运行时）同步由发布前检查和 plugin-sync（插件同步）处理。

2. Release Flow（发布流程）在发布前拦截 stale runtime（过期运行时）。

   preflight（发布预检）已经是发布前总入口，适合输出 `runtime_update_required` 并给更新命令。这样不会卡普通 `verify full`（全量验证），但会阻止带旧 runtime（运行时）发布。

3. plugin-sync（插件同步）保留授权边界。

   检查可以自动做，更新必须等用户授权。更新后只报告 diff（变更）和 PR Flow（拉取请求流程）下一步，不自动提交。

## Risks / Trade-offs

- [Risk] plugin-sync（插件同步）源码当前不在仓库内 → 实施前确认是否允许修改用户级 skill（技能）路径。
- [Risk] runtime（运行时）落后不阻塞普通验证 → 由 Release Flow preflight（发布预检）在发布前阻塞。
- [Risk] 版本扫描误伤假版本 fixture（测试夹具） → 允许极少数明确白名单，例如 `9.9.9`。
