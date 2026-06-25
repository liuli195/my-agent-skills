## Why（原因）

现有 `docs/adr`、`docs/changes`、`docs/designs`、`docs/plans` 和 `docs/prd` 混合保存当前契约、历史 issue 说明、技术设计和草案内容。仓库已经初始化 OpenSpec，需要把仍有效的 Agent Guard（代理守卫）事实整理为可校验的 OpenSpec baseline（基线），避免后续实现继续依赖散落文档和已被 ADR（架构决策记录）替代的旧契约。

## What Changes（变更内容）

- 建立 `agent-guard-core`、`agent-guard-plugin-runtime`、`agent-guard-brief-injection` 和 `agent-guard-skill-entrypoints` 四个 OpenSpec capability（能力）。
- 把当前有效契约写入 `openspec/specs/<capability>/spec.md`。
- 把本次迁移过程保留为 `baseline-agent-guard-docs-migration` change（变更）并归档。
- 补齐 `openspec/config.yaml`，使用默认 `spec-driven` schema（流程模式）。
- 不创建 `openspec/project.md`，因为当前 OpenSpec CLI（命令行工具）把它视为 legacy（旧结构）。
- 不删除旧 `docs/` 文件；它们暂时保留为来源证据。

## Capabilities（能力）

### New Capabilities（新增能力）

- `agent-guard-core`：Agent Guard（代理守卫）的核心模型、来源门禁、Guard Profile（守卫画像）、Runtime（运行时）边界、权限、初始化和验证契约。
- `agent-guard-plugin-runtime`：Plugin-first（插件优先）发布、固定 lifecycle Hook（生命周期钩子）、Session Observation（会话观察记录）、Session Focus（会话焦点）、Runtime Router（运行时路由器）和状态推进契约。
- `agent-guard-brief-injection`：Guard Brief（守卫简报）、Guard Injection（守卫注入）、`brief_hash` 去重、latest brief（最新简报）路径和 `brief_required` 状态推进门禁。
- `agent-guard-skill-entrypoints`：`$agent-guard` 薄路由入口、4 个场景入口、必需辅助动作和删除独立 `$agent-guard-hooks` 入口后的入口契约。

### Modified Capabilities（修改能力）

- 无；当前仓库没有既有 OpenSpec main specs（主规格）。

## Impact（影响范围）

- Affected docs（受影响文档）：`openspec/config.yaml`、`openspec/changes/baseline-agent-guard-docs-migration/**`、`openspec/specs/**`。
- Source docs（来源文档）：`docs/adr/**`、`docs/changes/**`、`docs/designs/**`、`docs/prd/**`、`docs/plans/index.md`。
- 不修改 Agent Guard Plugin（代理守卫插件）源码、Skill（技能）源码、测试或安装脚本。
