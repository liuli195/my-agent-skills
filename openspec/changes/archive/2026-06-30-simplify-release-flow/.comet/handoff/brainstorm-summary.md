# Brainstorm Summary

- Change: simplify-release-flow
- Date: 2026-06-30

## 确认的技术方案

采用最小删除方案：删除本地 release-plan（发布计划）、release record（发布记录）、仅服务 `/releases/` 的 `.release-flow/.gitignore` 和 summarize（摘要）流程；发布输入收敛为 `tag`（标签）、`version`（版本）、`bumpPlugins`（提升插件列表）；CI（持续集成）隔离执行正式 projection（投影）。`bumpPlugins: []` 表示只发布 catalog/projection（目录/投影）变化，不新增 `catalog-only`（仅目录）字段。单一 Plugin registry（插件注册表）替代 `versionFiles`（版本文件列表）和分裂的生成器列表。未声明插件的版本漂移基准是 `origin/<channelBranch>`（远端通道分支）中同路径 manifest（插件清单）版本。

## 关键取舍与风险

- 不实现 GitHub Rulesets（GitHub 规则集）检查，相关失败留到 CI（持续集成）push（推送）阶段暴露。
- 不在 `github-plan`（GitHub 配置方案）或 `configure-github`（配置 GitHub）中输出 GitHub Rulesets（GitHub 规则集）配置步骤。
- 不保留旧 release-plan（发布计划）兼容逻辑。
- 远端 tag/release（标签/发布）检查只使用现有 `git`（版本管理）和 `gh`（GitHub 命令行）。

## 测试策略

更新 release-flow（发布流程）脚本测试、workflow（工作流）输入测试和 build-and-verify（构建与验证）相关版本假设测试；最后运行 OpenSpec（开放规格）校验和仓库验证入口。

## Spec Patch

暂无候选 patch（补丁）。当前 delta spec（增量规格）已覆盖确认范围。
