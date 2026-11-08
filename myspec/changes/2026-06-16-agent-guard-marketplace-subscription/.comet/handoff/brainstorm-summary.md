# Brainstorm Summary

- Change: agent-guard-marketplace-subscription
- Date: 2026-06-17

## 确认的技术方案

- 发布入口收敛到 marketplace subscription（市场订阅）。
- 正式订阅源指向 GitHub repo（GitHub 仓库）的发布分支 `marketplace`，不使用 tag（标签）或 commit（提交）固定版本。
- 本仓库同时维护 Codex 与 Claude 两套 marketplace catalog（市场目录）：Codex 使用 `.agents/plugins/marketplace.json`，Claude 使用 `.claude-plugin/marketplace.json`。
- 两套 catalog 都指向同一个自包含插件目录 `plugins/agent-guard`。
- 插件包继续包含 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json`，并把运行所需的 skills、hooks、runtime、scripts 和 assets 保留在插件目录内。
- 不保留 user-level Skill installation（用户级技能安装）兼容层。
- 不保留 Claude Junction（Claude 目录联接）兼容层。
- Codex 本地 marketplace entry（市场条目）继续采用 `source` 对象、`policy.installation`、`policy.authentication` 和 `category`。
- installer（安装器）保留一个 CLI 入口，但内部拆分 package validation（包校验）、catalog validation/write（目录校验/写入）和 CLI orchestration（命令编排）。

## 关键取舍与风险

- 旧脚本删除是 breaking change（破坏性变更），需要测试断言旧入口不再存在。
- Claude personal/project marketplace（个人/项目市场）默认路径不在 installer 中硬编码；应通过 CLI 订阅源或显式参数表达。
- 发布分支是浮动引用，订阅者会跟随分支更新；需要用发布分支纪律替代 tag/commit 固定带来的可复现性。
- Claude 会复制插件目录到 cache，所以 `agent-guard` 插件包必须自包含，不能依赖插件目录外的共享文件。
- Codex 与 Claude 的 catalog schema（目录结构）不完全相同；实现阶段应分别序列化，但共享同一插件包和同一发布分支。

## 测试策略

- 先改测试表达新契约，再实现。
- installer tests 覆盖 dry-run、授权写入、verify、旧 entry 拒绝、`target`/`scope` 组合和 `marketplace` 发布分支。
- package tests 校验 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、hooks、runtime、skills 和自包含资源。
- runtime e2e 使用临时目录，不写真实用户目录。
- 定向扫描确认没有活跃文档或测试继续引用旧 user-level Skill installation 或 Claude Junction 作为发布契约。

## Spec Patch

- 回写 `agent-guard-plugin-runtime` delta spec：新增 GitHub repo 发布分支 `marketplace` 作为正式 marketplace source（市场来源）的验收场景。
- 回写 `agent-guard-plugin-runtime` delta spec：明确维护 Codex `.agents/plugins/marketplace.json` 与 Claude `.claude-plugin/marketplace.json` 两个 catalog（目录），共享同一个自包含插件目录 `plugins/agent-guard`。
