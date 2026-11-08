## Context

当前 release-flow 已能用 `.release-flow/config.yaml`、`.release-flow/projection.yaml` 和 GitHub workflow 生成 `marketplace` 分支，但 marketplace identity（市场身份）仍分散在多个位置：

- `.agents/plugins/marketplace.json` 和 `.claude-plugin/marketplace.json` 中保存正式 marketplace name。
- `.release-flow/projection.yaml` 只声明变量名和 JSON Pointer（JSON 指针），尚未把 project projection（项目投影）扩展为 identity 的权威来源。
- GitHub workflow 已隐式使用 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF`，但配置模板、期望设置输出和 preflight 没有明确要求它们。
- Agent Guard installer 仍硬编码 `my-agent-skills-marketplace` 默认值，无法发现旧名残留或和 release-flow identity 不一致。

这导致 main 分支打开时可能被 Codex Desktop 识别为 repo-local marketplace（仓库本地市场），同时正式订阅又指向同名 marketplace。

## Goals / Non-Goals

**Goals:**

- 建立一个单一 marketplace identity 注册位置，作为 release-flow 和 installer 的共同事实源。
- 让 release-flow 模板、GitHub expected settings（期望设置）、workflow、preflight 和发布分支生成都使用同一 identity。
- 让 main 分支不再需要持久保存 Codex repo-local marketplace 文件；发布分支仍由 release workflow 生成该文件。
- 明确校验 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF`，并在缺失时给出修复步骤。
- 增加测试覆盖 identity 一致、缺失、漂移、旧名残留和源分支无 Codex marketplace 的路径。

**Non-Goals:**

- 不实现真实 GitHub Settings API 写入或远端设置回读。
- 不改变 installer 的授权模型；仍然需要显式 scope、target 和 install authorization。
- 不把 release-flow 脚本复制到目标项目。
- 不把 GitHub Actions Variables 的真实值写入 Git。

## Decisions

### Decision: identity 放在 `.release-flow/projection.yaml`，按领域归属到项目投影

采用 `.release-flow/projection.yaml` 内的 `identity` 或等价 project projection 区域作为权威来源，字段覆盖：

- Codex marketplace catalog name 和 display name。
- Claude marketplace catalog name 和 owner name。
- release-flow plugin repository 和 ref。
- 可选的 expected plugin entries（插件条目）名称列表，用于验证生成结果。

`config.yaml` 保持仓库级 release-flow 通用配置：source ref、channel branch、workflow、records、GitHub policy、manifest files。Marketplace identity 是当前项目如何投影成发布市场的项目逻辑，归属 `projection.yaml`。

### Decision: projection 同时描述 identity 和如何注入，但保持值与变量分离

Projection 负责三类同一领域的声明：identity（应该发布成什么身份）、variables（哪些 GitHub Actions Variables 必须存在）、transforms/generators（如何生成或注入）。`github-plan`、`configure-github --dry-run` 和 `preflight` 从 projection 合成必需 GitHub Actions Variables 清单。

这样可以继续保留“Git 不保存变量真实值”的安全边界，同时让缺变量错误能说明变量含义和手动配置步骤。Identity 字段本身只保存非敏感期望值或变量引用，不保存 secret。

### Decision: Codex marketplace 由发布模板生成，main 不持久保存

对 `.agents/plugins/marketplace.json` 使用 release-flow 模板或内置 catalog 生成路径。发布时即使 source branch（源分支）没有该文件，也能在 projected tree（投影树）中生成正式 marketplace catalog。

Claude marketplace 是否继续作为 repo-local 文件由后续实现按当前兼容性决定，但 Codex 的 repo-local marketplace 必须从 main 移除，避免 Codex Desktop 误识别本仓库为本地 marketplace。

### Decision: installer 读取共享 identity，但 repo scope 行为不扩散

Agent Guard installer 的默认 marketplace catalog root 和 verify 期望从共享 identity 读取；如果调用方显式传入 repo marketplace 路径，installer 仍可按 repo scope 写入目标项目 catalog。

本仓库 main 分支不保留 Codex repo-local marketplace，不等于禁止目标项目使用 repo scope 安装。

## Risks / Trade-offs

- [Risk] projection 语义扩展后，旧 projection 缺少 identity 字段。  
  Mitigation: preflight 和 validate 输出清晰缺字段错误，并在 projection 模板中提供默认结构。
- [Risk] 源分支缺少 `.agents/plugins/marketplace.json` 后，现有投影逻辑若只会修改已有 JSON 会失败。  
  Mitigation: 增加 generate-from-template 路径和回归测试，覆盖“源分支无文件，发布分支生成文件”。
- [Risk] release-flow、installer 和 tests 同时改动，范围容易扩大。  
  Mitigation: 只改 marketplace identity、变量声明和生成/校验路径，不重构插件安装模型。
- [Risk] GitHub 变量缺失检查可能被误解为远端设置已验证。  
  Mitigation: 保持首版边界：preflight 使用传入变量快照或手动步骤，不声称真实回读 GitHub Rulesets 或 workflow permissions。

## Migration Plan

1. 在 `.release-flow/projection.yaml` 和 release-flow projection 模板中声明 marketplace identity。
2. 让 workflow/preflight/GitHub 配置方案从 projection identity 派生必需变量，补充 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF`。
3. 为 Codex marketplace 增加发布模板生成路径，移除 main 分支持久 Codex marketplace 文件。
4. 让 Agent Guard installer 默认值和验证读取 identity。
5. 更新测试和文档，跑 release-flow 与 agent-guard 相关端到端回归。

Rollback（回滚）方式：保留旧 projection 变量和 marketplace 模板测试；若新 identity 校验阻塞发布，可在同一 change 中恢复旧 marketplace 文件并标记配置迁移未完成。

## Open Questions

无。当前按单一 change 处理 #38、#39、#40；三者共享同一 identity 链路，拆分会重复改同一批文件。
