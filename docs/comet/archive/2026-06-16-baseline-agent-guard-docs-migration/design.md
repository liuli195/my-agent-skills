## Context（上下文）

仓库内旧文档已经覆盖 Agent Guard（代理守卫）的需求、设计、ADR（架构决策记录）和 issue（议题）变更说明，但这些文档不是 OpenSpec 可校验格式。`openspec list --specs --json` 在迁移前没有 main spec（主规格），`openspec validate --all --strict --json` 也只校验到 0 个对象。

本次迁移的目标是建立 OpenSpec baseline（基线），不是重写实现。旧文档中有部分内容已被 ADR 0002 替代，例如 Subject Resolver（主体解析器）、`subject_key_hash` 身份路径、Git Hook（Git 钩子）第一版兜底、项目级复制 Runtime code（运行时代码）。这些旧契约只作为来源背景，不进入当前 baseline specs（基线规格）。

## Goals / Non-Goals（目标 / 非目标）

**Goals（目标）：**

- 建立 4 个可由 OpenSpec strict validation（严格校验）通过的 main specs（主规格）。
- 保留本次迁移的 proposal（提案）、design（设计）、tasks（任务）和 delta specs（增量规格）。
- 明确旧文档到 OpenSpec capability（能力）的映射。
- 以 ADR 0002 的 accepted（已接受）决策覆盖旧草案里的替代内容。

**Non-Goals（非目标）：**

- 不删除或改写旧 `docs/` 文档。
- 不修改 Plugin（插件）、Skill（技能）、Runtime（运行时）或测试实现。
- 不创建 `openspec/project.md`。
- 不把旧 issue（议题）重新恢复为 active change（活动变更）。

## Decisions（决策）

- OpenSpec 目录使用当前 CLI（命令行工具）认可的结构：`openspec/config.yaml`、`openspec/specs/<capability>/spec.md`、`openspec/changes/<change>/...` 和 `openspec/changes/archive/YYYY-MM-DD-<change>/...`。
- main spec（主规格）使用 `## Purpose` + `## Requirements`；delta spec（增量规格）使用 `## ADDED Requirements`。
- Requirement（需求）正文必须包含 `MUST` 或 `SHALL`，Scenario（场景）必须使用 `#### Scenario:` 四级标题。
- `agent-guard-core` 只沉淀未被 ADR 0002 替代的核心契约：确认调研来源、Guard Profile（守卫画像）业务语义、Runtime（运行时）通用边界、状态权限、初始化边界和画像验证。
- `agent-guard-plugin-runtime` 以 ADR 0002、PRD（产品需求文档）0017、Design（设计）0017 和 `docs/changes` 0021-0029 为准，记录 Plugin-first（插件优先）、`SessionStart`、`PreToolUse`、Session Focus（会话焦点）和当前实例状态推进。
- `agent-guard-brief-injection` 以 PRD 0030、Design 0030 和 ADR 0002 为准，记录 latest brief（最新简报）、pull-to-inject（读取触发注入）、`brief_hash` 和 `brief_required`。
- `agent-guard-skill-entrypoints` 以 issues（议题）0018、0020 和 0031 为准，记录入口拆分、必需流程句和删除 `$agent-guard-hooks`。

## Risks / Trade-offs（风险 / 取舍）

- 旧 PRD 包含大量历史设计，直接复制会把过时契约带入 baseline（基线）。缓解：每条 requirement（需求）只写当前有效行为，并在 design（设计）中说明替代依据。
- OpenSpec 需求文本过长会降低可读性。缓解：按 capability（能力）拆分，requirements（需求）保持行为级表达，细节留在 scenario（场景）和旧文档来源。
- 旧 docs（文档）暂时保留可能让未来读者混淆权威来源。缓解：本次先建立 OpenSpec 权威基线，后续单独 cleanup change（清理变更）处理旧 docs 跳转或归档。

## Migration Plan（迁移计划）

1. 创建 `baseline-agent-guard-docs-migration` active change（活动变更）。
2. 写入 proposal（提案）、design（设计）、tasks（任务）和 4 个 delta specs（增量规格）。
3. 运行 `openspec validate baseline-agent-guard-docs-migration --type change --strict --json`。
4. 按 `openspec-sync-specs` 规则把 delta specs 同步为 main specs（主规格）。
5. 运行 `openspec validate --specs --strict --json` 和 `openspec validate --all --strict --json`。
6. 将任务标记为完成。
7. 使用 `openspec archive baseline-agent-guard-docs-migration --skip-specs -y` 归档，避免重复应用已经同步的 main specs。

## Open Questions（开放问题）

无阻塞问题。旧 `docs/` 的删除、跳转或归档说明应通过后续独立 cleanup change（清理变更）决定。
