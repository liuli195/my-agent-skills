## Why

Release Flow（发布流程）当前把一次发布拆成过多本地步骤，并要求所有 Plugin（插件）一起 bump（提升版本）。这导致 catalog（目录）变更、单插件发布、发布记录清理、发布摘要补齐和投影污染都反复消耗人工确认成本。

## What Changes

- **BREAKING** 删除旧 release-plan（发布计划）兼容逻辑，发布输入改为 `tag`、`version` 和必填 `bumpPlugins`（提升插件列表）。
- **BREAKING** 删除 `release-init`（发布初始化）在 CI（持续集成）里的重复运行和 workflow（工作流）的 `releasePlan`（发布计划文件）输入。
- **BREAKING** 删除 `.release-flow/config.yaml`（配置文件）里的 `versionFiles`（版本文件列表）和本地 `records`（记录）配置。
- 删除本地 `summarize`（发布摘要）和 `.release-flow/releases/<tag>/` 持久 release record（发布记录）。
- 删除 `catalog-only`（仅目录）专门模式，用 `bumpPlugins: []` 表达不提升任何插件。
- 统一 Codex marketplace（Codex 市场）插件注册表，避免 projection（投影）、生成器和 manifest（插件清单）列表分裂。
- preflight（发布前检查）只验证必要发布条件，并检查远端 tag（标签）和 GitHub Release（GitHub 发布）是否已存在。
- 发布 projection（投影）只在 CI（持续集成）隔离环境执行，本地 DEV（开发）marketplace（市场）配置不被正式发布身份污染。
- CI（持续集成）发布完成后直接输出 release URL（发布链接）、marketplace commit（市场提交）、tag commit（标签提交）和 workflow run URL（工作流运行链接）。
- 不实现 GitHub Rulesets（GitHub 规则集）检查，#44 按删除需求处理。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `release-flow-plugin`: 收敛发布输入、发布前检查、CI（持续集成）发布、投影执行位置和发布结果追溯。

## Impact

- Affected code（受影响代码）: `plugins/release-flow/skills/release-flow/scripts/release_flow.py`
- Affected config（受影响配置）: `.release-flow/config.yaml`, `.release-flow/projection.yaml`
- Affected workflow（受影响工作流）: `.github/workflows/release.yml`
- Affected tests（受影响测试）: release-flow（发布流程）和 build-and-verify（构建与验证）相关测试
- Dependencies（依赖）: 不新增依赖
