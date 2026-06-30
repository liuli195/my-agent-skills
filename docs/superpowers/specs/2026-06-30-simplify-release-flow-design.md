---
comet_change: simplify-release-flow
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-30-simplify-release-flow
status: final
---

# Simplify Release Flow Design

## Context

Release Flow（发布流程）当前把一次发布拆成本地 release-init（发布初始化）、preflight（发布前检查）、publish（发布）、CI（持续集成）发布、summarize（摘要）和人工 cleanup（清理）。这个模型让 catalog（目录）变更和单插件发布也要 bump（提升版本）全部插件，并反复产生 ignored（忽略）的本地 release record（发布记录）。

本次设计按最小删除原则处理：本地只做检查和触发，正式发布产物只在 CI（持续集成）隔离环境生成。

## Confirmed Approach

发布输入只保留三项：

- `tag`（标签）
- `version`（版本）
- `bumpPlugins`（提升插件列表）

`bumpPlugins`（提升插件列表）必填。非空列表表示只提升这些插件；空列表表示不提升任何插件，只发布 catalog/projection（目录/投影）变化。不新增 `catalog-only`（仅目录）字段。

删除本地 release-plan（发布计划）、release record（发布记录）、仅服务 `/releases/` 的 `.release-flow/.gitignore`、`release-init`（发布初始化）命令和 `summarize`（摘要）。`publish`（发布）不再读取 `.release-flow/releases/<tag>/release-plan.json`，而是直接把三项输入传给 GitHub Workflow（GitHub 工作流）。

建立单一 Plugin registry（插件注册表）。projection（投影）校验、Codex marketplace（Codex 市场）生成和 manifest（插件清单）版本路径都从该注册表推导，不再维护 `.release-flow/config.yaml`（配置文件）里的 `versionFiles`（版本文件列表）。

preflight（发布前检查）验证：

- `tag`（标签）和 `version`（版本）一致。
- `bumpPlugins`（提升插件列表）存在，且只包含已注册插件。
- 声明提升的插件 manifest（插件清单）版本等于发布版本。
- 未声明提升的插件 manifest（插件清单）版本等于 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）版本。
- projection（投影）可由单一注册表生成。
- 远端 tag（标签）和 GitHub Release（GitHub 发布）尚不存在。

CI（持续集成）发布前重复必要检查，随后在 isolated release tree（隔离发布树）中执行正式 projection（投影），推送 `marketplace`（市场分支）、创建 tag（标签）和 GitHub Release（GitHub 发布），并输出 release URL（发布链接）、marketplace commit（市场提交）、tag commit（标签提交）和 workflow run URL（工作流运行链接）。

## Non-Goals

- 不实现 GitHub Rulesets（GitHub 规则集）检查。
- 不在 `github-plan`（GitHub 配置方案）或 `configure-github`（配置 GitHub）中输出 GitHub Rulesets（GitHub 规则集）配置步骤。
- 不保留旧 release-plan（发布计划）兼容逻辑。
- 不新增 cleanup（清理）命令。
- 不保留本地 release summary（发布摘要）。
- 不新增依赖。

## Trade-offs

Rulesets（规则集）冲突不会提前在 preflight（发布前检查）发现，失败会留到 CI（持续集成）push（推送）阶段暴露。这符合 #44 删除需求后的边界。

旧 release-plan（发布计划）格式会失效。这是有意 breaking change（破坏性变更），因为兼容层会让流程继续保留两套输入。

远端发布冲突检查只使用已有 `git`（版本管理）和 `gh`（GitHub 命令行）。如果认证或网络不可用，检查必须报告 unknown（未知）并失败，不能假装已确认。

未声明版本漂移的比较基准是 `origin/<channelBranch>`（远端通道分支）。如果该远端基准不可读取，preflight（发布前检查）失败并报告 remote baseline unknown（远端基准未知）。

## Test Strategy

测试覆盖四类行为：

- release-flow（发布流程）输入：部分插件提升、空 `bumpPlugins`（提升插件列表）、未知插件拒绝。
- 版本检查：声明插件必须等于发布版本，未声明插件版本漂移必须失败。
- 发布触发：workflow（工作流）输入不再包含 `releasePlan`（发布计划文件），只传三项输入。
- CI（持续集成）发布：重复远端冲突检查，输出发布追溯字段。
- 端到端回归：从用户入口跑 preflight（发布前检查）和 publish dry-run（发布试运行），并覆盖 CI（持续集成）发布形态的隔离 projection（投影）、无本地 Git（版本管理）写入和追溯字段输出。

构建验证使用本仓库现有 Build and Verify（构建与验证）入口，不新增验证框架。
