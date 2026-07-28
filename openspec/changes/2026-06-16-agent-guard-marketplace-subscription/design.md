## Context

Agent Guard Plugin（代理守卫插件）当前已经采用 Plugin-first（插件优先）架构：runtime（运行时）、hook router（钩子路由器）、hooks（钩子）和 Skill（技能）入口都位于 `plugins/agent-guard/`。但发布路径仍不干净：

- 插件包已有 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json`。
- `install_agent_guard_plugin.py` 当前写入 `codex_home/plugins/agent-guard`、`claude_home/plugins/agent-guard`，并维护简单的 `marketplace.json`。
- `scripts/install/` 仍维护 user-level Skill（用户级技能）同步和 Claude Junction（目录联接）兼容层。
- `agent-guard-skill-entrypoints` spec 仍要求 user-level Skill installation verification（用户级技能安装验证）。

这些路径会让“插件订阅”和“技能复制”同时成为发布契约，导致 Codex 与 Claude 的安装面不一致。

## Goals / Non-Goals

**Goals:**

- 以 marketplace subscription（市场订阅）作为 Agent Guard 的唯一发布/订阅入口。
- 同一个 `plugins/agent-guard` 包同时提供 Codex 和 Claude 可验证 manifest（清单）。
- 支持 personal marketplace（个人市场）和 repo marketplace（仓库市场）。
- 保留 dry-run（试运行）默认行为，所有写入仍需显式授权。
- 更新 OpenSpec specs、安装器、测试和文档，删除旧 user-level Skill/Junction 契约。

**Non-Goals:**

- 不实际安装到当前用户的 Codex 或 Claude 目录。
- 不配置用户环境、不创建 Hook（钩子）、不初始化 Guard Profile（守卫画像）。
- 不新增 runtime（运行时）业务语义。
- 不保留旧 user-level Skill 安装脚本作为兼容层。

## Decisions

### 1. Marketplace 是唯一发布入口

Agent Guard 的订阅入口改为 marketplace entry（市场条目），不再把 `.agents/skills/*` 同步当作发布动作。

替代方案：

- 保留 user-level Skill 安装作为兼容层：迁移成本低，但继续制造两套入口。
- 只支持 Codex marketplace：实现小，但不满足 Claude 目标。
- 统一 marketplace 订阅：契约清楚，测试可直接覆盖个人/仓库两类入口。

选择统一 marketplace 订阅，因为它和 Plugin-first 基线一致。

### 2. GitHub 发布分支是正式订阅源

Agent Guard 的正式 marketplace subscription（市场订阅）指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本。

替代方案：

- 使用 tag 或 commit 固定版本：可复现性更强，但不符合本 change 的订阅更新策略。
- 使用主开发分支：操作简单，但发布纪律不清晰。
- 使用独立发布分支：订阅入口稳定，发布内容可以独立验证后推进。

选择 `marketplace` 发布分支，因为它贴近 Codex 和 Claude 的 GitHub marketplace 使用方式，同时避免把开发分支直接暴露给订阅者。

### 3. Codex 与 Claude 维护双 catalog，共享同一插件包

仓库内同时维护：

- Codex marketplace catalog（市场目录）：`.agents/plugins/marketplace.json`
- Claude marketplace catalog（市场目录）：`.claude-plugin/marketplace.json`

两套 catalog 都解析到同一个自包含插件包 `plugins/agent-guard`。插件包内部包含 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、skills、hooks、runtime、scripts 和 assets。Claude 安装会复制插件目录到 cache（缓存），所以插件包不能依赖目录外文件。

### 4. Codex 本地 marketplace entry 保持当前 schema（条目结构）

Codex personal/repo marketplace 使用当前 marketplace entry：

```json
{
  "name": "agent-guard",
  "source": {
    "source": "local",
    "path": "./plugins/agent-guard"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

Personal marketplace 默认位于用户侧 marketplace root；repo marketplace 位于仓库内 `.agents/plugins/marketplace.json`。两者都使用 `./plugins/agent-guard`，由 marketplace 文件位置决定解析根。

Claude catalog 使用 Claude 自己的 `.claude-plugin/marketplace.json` schema，不强行复用 Codex entry 字段；实现阶段必须分别序列化，但共享插件包、插件名和发布分支。

### 5. Target（目标）与 scope（作用域）分开建模

安装器参数应区分：

- `--target codex|claude|all`：决定校验 `.codex-plugin`、`.claude-plugin` 或两者。
- `--scope personal|repo|all`：决定写入/验证个人 marketplace、仓库 marketplace 或两者。

这样可以表达“只为 Codex 写 repo marketplace”或“同时验证 Codex/Claude 的 personal 和 repo marketplace”，避免把产品目标和安装位置混在一起。

### 6. 旧安装脚本从契约中删除

`scripts/install/install_user_skill.ps1`、`scripts/install/sync_claude_junction.ps1`、`scripts/install/verify_install.py` 及其测试不再作为 Agent Guard 发布契约。实现可以删除这些文件，或先将测试改为断言它们不存在；最终状态应不再暴露旧入口。

### 5. Manifest 校验保持产品感知

插件包必须继续包含 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json`。Marketplace entry 只声明来源和策略；产品特定能力由对应 manifest 校验。

## Risks / Trade-offs

- [Risk] 发布分支是浮动引用，订阅者会跟随分支更新。→ Mitigation: 只有验证通过的内容进入 `marketplace` 发布分支。
- [Risk] Claude marketplace 的外部约定和 Codex marketplace 不完全一致。→ Mitigation: 分别序列化 Codex 与 Claude catalog，只共享插件包和发布分支。
- [Risk] 删除旧 user-level Skill 脚本会破坏手动安装习惯。→ Mitigation: 这是明确 breaking change（破坏性变更），用 tests 和 docs 指向 marketplace subscription。
- [Risk] personal marketplace 写入用户目录有副作用。→ Mitigation: dry-run 默认不写入；授权安装测试使用临时目录；真实安装仍需用户显式授权。

## Migration Plan

1. 先更新 specs，明确旧 user-level Skill/Junction 契约移除。
2. 更新 installer（安装器）和 tests，覆盖 personal/repo marketplace entry。
3. 删除旧 user-level Skill 安装脚本和测试，或改为断言旧入口不存在。
4. 运行 OpenSpec strict validation（严格校验）和相关 pytest（测试）。

Rollback（回滚）策略：如果实现阶段发现 Claude marketplace 需要独立结构，保留 Plugin-first、发布分支和旧路径删除决策，只调整 Claude catalog serialization（目录序列化）并同步 specs。
