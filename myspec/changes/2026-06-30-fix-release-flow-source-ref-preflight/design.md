## Context

Release Flow（发布流程）在 `preflight`（发布前检查）中已经验证本地 manifest（清单）版本、远端发布通道基准、projection（投影）和远端 tag/release（标签/发布）冲突。缺口是它没有检查配置里的 `sourceRef`（源引用）是否已经包含本次版本提升，导致维护者在受保护 `main`（主干分支）上补版本提交时撞上 PR（拉取请求）保护。

## Goals / Non-Goals

**Goals:**

- 复用现有 `preflight`（发布前检查）入口阻止未进入远端 `sourceRef`（源引用）的版本提升发布。
- 复用现有 Plugin registry（插件注册表）、manifest（清单）路径和 `git show`（版本管理查看文件）模式。
- 输出可行动错误，指向现有 PR Flow（拉取请求流程）。

**Non-Goals:**

- 不让 Release Flow（发布流程）创建或合并 PR（拉取请求）。
- 不新增 hotfix（热修复）直写路径或绕过展示。
- 不新增依赖或配置字段。

## Decisions

- 在 `preflight_errors()`（发布前检查错误）中加入 `sourceRef`（源引用）版本校验。原因：这是现有发布前入口，避免第二套检查。
- 对 `bumpPlugins`（提升插件列表）才校验远端 `sourceRef`（源引用）版本。原因：未提升插件已有远端发布通道漂移检查。
- 使用 `git show origin/<sourceRef>:<manifest>` 读取远端源码分支。原因：仓库已有 `remote_manifest_version()`（远端清单版本）同类实现。

## Risks / Trade-offs

- `origin/<sourceRef>`（远端源引用）不可读取会让 preflight（发布前检查）失败 -> 这是正确失败，避免假装可发布。
