## Context

当前 Release Flow（发布流程）有三个成本高的来源：

- 本地 release-plan（发布计划）和 release record（发布记录）把一次发布拆成多步，发布后还要人工清理和补摘要。
- 所有 Plugin（插件）版本都由 tag（标签）统一约束，导致 catalog（目录）变更和单插件发布也要 bump（提升版本）全部 manifest（插件清单）。
- projection（投影）、marketplace（市场）生成和 manifest（插件清单）路径来自多个列表，新增插件时容易漏一处。

本次改动按最小方案处理：删除可选流程，保留本地检查和触发，把正式发布产物放到 CI（持续集成）隔离环境生成。

## Goals / Non-Goals

**Goals:**

- 支持 `bumpPlugins`（提升插件列表）表达部分插件发布和 `[]` 的目录-only（仅目录）发布。
- 删除本地持久 release record（发布记录）、`.release-flow/.gitignore` 中仅服务 `/releases/` 的残留、`summarize`（发布摘要）和 `cleanup`（清理）需求。
- 删除 `release-init`（发布初始化）本地命令、旧 release-plan（发布计划）路径、文档、模板、测试引用和 CI（持续集成）重复调用。
- 用单一 Plugin registry（插件注册表）驱动 projection（投影）校验、marketplace（市场）生成和 manifest（插件清单）路径。
- preflight（发布前检查）提前发现远端 tag（标签）或 GitHub Release（GitHub 发布）已存在。
- 发布 projection（投影）只在 CI（持续集成）隔离发布树运行，避免污染源码分支 DEV（开发）marketplace（市场）配置。

**Non-Goals:**

- 不实现 GitHub Rulesets（GitHub 规则集）读取或验证。
- 不在 `github-plan`（GitHub 配置方案）或 `configure-github`（配置 GitHub）中输出 GitHub Rulesets（GitHub 规则集）配置步骤。
- 不保留旧 release-plan（发布计划）格式兼容。
- 不新增依赖。
- 不新增 release cleanup（发布清理）命令。
- 不维护本地 release summary（发布摘要）文件。

## Decisions

1. 发布输入只保留 `tag`、`version`、`bumpPlugins`（提升插件列表）。
   - `bumpPlugins` 必填。
   - `[]` 表示不提升任何插件，只发布 catalog（目录）或 projection（投影）变化。
   - 不再引入 `catalog-only`（仅目录）字段，避免两个字段表达同一件事。

2. 删除 `.release-flow/config.yaml`（配置文件）里的 manifest list（清单列表）和 records（记录）配置。
   - manifest（插件清单）路径从单一 Plugin registry（插件注册表）和 projection（投影）插件列表推导。
   - 本地 `.release-flow/releases/<tag>/` 不再是流程的一部分。
   - 仅服务 `.release-flow/releases/`（发布记录目录）的 `.release-flow/.gitignore` 一并删除。

3. CI（持续集成）是唯一正式 projection（投影）执行位置。
   - 本地 `preflight`（发布前检查）只验证输入、配置、版本漂移和远端 tag/release（标签/发布）冲突。
   - 版本漂移基准是 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）的版本；未声明插件必须与该版本一致。
   - `ci-publish`（持续集成发布）在 orphan branch（孤立分支）发布树中执行 projection（投影），再推送 `marketplace`（市场分支）、tag（标签）和 GitHub Release（GitHub 发布）。
   - 源码分支中的 DEV（开发）marketplace（市场）配置不被正式 marketplace（市场）身份覆盖。

4. 发布结果追溯只走 CI（持续集成）输出。
   - `ci-publish`（持续集成发布）输出 release URL（发布链接）、marketplace commit（市场提交）、tag commit（标签提交）和 workflow run URL（工作流运行链接）。
   - 不再生成本地 `release-summary.md`（发布摘要）。

## Risks / Trade-offs

- Rulesets（规则集）冲突不会在 preflight（发布前检查）提前发现 -> 接受；#44 已按删除需求处理，失败会发生在 CI（持续集成）push（推送）阶段。
- 删除兼容逻辑会让旧 release-plan（发布计划）无法发布 -> 接受；本仓库明确要求不保留兼容逻辑。
- 远端 GitHub Release（GitHub 发布）检查依赖 `gh` CLI（GitHub 命令行）认证 -> 输出 unknown（未知）状态并失败，不新增 API（接口）客户端。
- 版本漂移检查依赖远端发布通道可读取 -> 如果无法读取 `origin/<channelBranch>`（远端通道分支）基准，preflight（发布前检查）失败并提示远端基准未知。
- 单一 registry（注册表）仍需要维护插件元数据 -> 比三个分裂列表少，且能由测试覆盖。
