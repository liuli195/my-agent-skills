---
comet_change: agent-guard-marketplace-subscription
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-16-agent-guard-marketplace-subscription
status: final
---

# Agent Guard Marketplace Subscription 技术设计

## 背景

Agent Guard 已经是 Plugin-first（插件优先）结构，但安装面仍混有 user-level Skill installation（用户级技能安装）和 Claude Junction（Claude 目录联接）。本 change 将发布和订阅入口统一到 marketplace subscription（市场订阅）。

## 已确认决策

- 正式订阅源使用 GitHub repo（GitHub 仓库）的发布分支 `marketplace`。
- 不使用 tag（标签）或 commit（提交）作为用户订阅引用。
- 本仓库维护两套 marketplace catalog（市场目录）：Codex 使用 `.agents/plugins/marketplace.json`，Claude 使用 `.claude-plugin/marketplace.json`。
- 两套 catalog 都指向同一个自包含插件包 `plugins/agent-guard`。
- 不保留 user-level Skill installation（用户级技能安装）兼容层。
- 不保留 Claude Junction（Claude 目录联接）兼容层。

## 目标架构

`plugins/agent-guard` 是唯一插件包根目录，内部包含 Codex 和 Claude 各自的 manifest（清单）、skills（技能）、hooks（钩子）、runtime（运行时）、scripts（脚本）和 assets（资源）。Claude 安装时会复制插件目录到 cache（缓存），所以插件不能依赖目录外共享文件。

Codex catalog 位于 `.agents/plugins/marketplace.json`，使用 Codex 当前 marketplace entry（市场条目）结构：`source` 对象、`policy.installation`、`policy.authentication` 和 `category`。Claude catalog 位于 `.claude-plugin/marketplace.json`，按 Claude marketplace schema（市场结构）表达同一个 `agent-guard` 插件。

发布分支 `marketplace` 是订阅入口，不是单个本地 entry 字段。用户侧订阅命令指向 GitHub repo 的 `marketplace` 分支；catalog 内的插件路径解析到 `plugins/agent-guard`。

## Installer 边界

`install_agent_guard_plugin.py` 保留为一个 CLI 入口，但内部拆成三类职责：

- package validation（包校验）：校验 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、hooks、runtime 和 skills。
- catalog validation/write（目录校验/写入）：按 `target` 和 `scope` 生成或验证对应 marketplace catalog。
- CLI orchestration（命令编排）：处理 dry-run、install authorization（安装授权）、verify（验证）和输出。

参数模型保持产品目标和安装作用域分离：

- `--target codex|claude|all`
- `--scope personal|repo|all`

默认行为仍是 dry-run（试运行），不写真实用户目录。真实写入必须有明确授权。installer 不初始化 Guard Profile（守卫画像）、不写 project hooks（项目钩子）、不改 git config（Git 配置）。

## 数据流

1. 维护者在主开发分支修改 `plugins/agent-guard`。
2. 验证通过后，将发布内容推进到 GitHub `marketplace` 分支。
3. Codex 用户订阅 GitHub repo 的 `marketplace` 分支，并安装 `agent-guard`。
4. Claude 用户订阅同一 GitHub repo 的 `marketplace` 分支，并安装 `agent-guard`。
5. 两个产品读取各自 catalog，但最终解析到同一个自包含插件包。

## 测试策略

- 先更新 tests 表达新契约，再改实现。
- installer tests 覆盖 dry-run、授权写入、verify、旧 entry 拒绝、`target`/`scope` 组合和发布分支。
- package tests 校验 Codex/Claude manifest、hooks、runtime、skills 和自包含资源。
- runtime e2e 使用临时目录，避免写真实用户目录。
- 定向扫描确认活跃文档和测试不再把 user-level Skill installation 或 Claude Junction 当作发布契约。

## Spec Patch

- `agent-guard-plugin-runtime`：新增 GitHub repo 发布分支 `marketplace` 作为正式 marketplace source（市场来源）的验收场景。
- `agent-guard-plugin-runtime`：明确 Codex `.agents/plugins/marketplace.json` 与 Claude `.claude-plugin/marketplace.json` 双 catalog，并共享 `plugins/agent-guard`。

## 风险

发布分支是浮动引用，订阅者会跟随分支更新。这个方案用发布分支纪律替代 tag/commit 固定带来的可复现性，后续实现需要确保只有验证通过的内容进入 `marketplace` 分支。

Codex 与 Claude 的 marketplace schema 不完全相同。实现阶段应分别序列化 catalog，但不能分叉插件包内容。
