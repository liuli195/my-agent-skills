## 1. 配置和发布输入

- [x] 1.1 精简 `.release-flow/config.yaml`（配置文件），删除 `versionFiles`（版本文件列表）、本地 records（记录）配置、GitHub Rulesets（GitHub 规则集）配置和仅服务 `/releases/` 的 `.release-flow/.gitignore`
- [x] 1.2 删除 `release-init`（发布初始化）本地命令、旧 release-plan（发布计划）路径、文档、模板、测试引用和 CI（持续集成）重复调用
- [x] 1.3 将 preflight（发布前检查）、publish（发布）和 ci-publish（持续集成发布）输入收敛为 `tag`、`version`、`bumpPlugins`（提升插件列表）

## 2. 注册表和发布前检查

- [x] 2.1 建立单一 Plugin registry（插件注册表），复用到 projection（投影）校验、marketplace（市场）生成和 manifest（插件清单）版本检查
- [x] 2.2 实现 `bumpPlugins`（提升插件列表）版本检查；未声明插件必须等于 `origin/<channelBranch>`（远端通道分支）同路径 manifest（插件清单）版本，否则拒绝
- [x] 2.3 增加远端 tag（标签）和 GitHub Release（GitHub 发布）存在性检查，不实现 Rulesets（规则集）检查
- [x] 2.4 从 `github-plan`（GitHub 配置方案）和 `configure-github`（配置 GitHub）输出中删除 GitHub Rulesets（GitHub 规则集）配置步骤

## 3. CI 发布和投影隔离

- [x] 3.1 调整 GitHub Workflow（GitHub 工作流）输入，移除 `releasePlan`（发布计划文件），传递 `bumpPlugins`（提升插件列表）
- [x] 3.2 确保正式 projection（投影）只在 CI（持续集成）隔离发布树执行，本地源码 DEV（开发）marketplace（市场）配置不被污染
- [x] 3.3 删除本地 `summarize`（发布摘要）和 release record（发布记录）写入，改为 CI（持续集成）输出追溯字段

## 4. 测试和验证

- [x] 4.1 更新 release-flow（发布流程）测试覆盖部分插件提升、空 `bumpPlugins`（提升插件列表）、远端冲突和未注册插件
- [x] 4.2 更新 build-and-verify（构建与验证）相关测试，删除硬编码全插件版本常量假设
- [x] 4.3 增加端到端回归覆盖：从用户入口执行 preflight（发布前检查）和 publish dry-run（发布试运行），并覆盖 CI（持续集成）发布形态的隔离 projection（投影）、无本地 Git（版本管理）写入和追溯字段输出
- [x] 4.4 运行 OpenSpec（开放规格）校验和本仓库对应构建验证
