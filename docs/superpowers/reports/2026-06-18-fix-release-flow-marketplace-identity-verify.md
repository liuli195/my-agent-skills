# fix-release-flow-marketplace-identity 验证报告

日期：2026-06-18

## 结论

实现验证通过；分支处理尚未完成。按仓库规则，提交、推送、创建 PR 或归档都需要用户单独确认。

## 验证摘要

| 维度 | 结果 | 证据 |
| --- | --- | --- |
| Completeness | PASS | OpenSpec tasks 16/16 已完成；2 个 delta spec 已读取对照 |
| Correctness | PASS | release-flow 与 Agent Guard installer 相关端到端回归 72/72 通过 |
| Coherence | PASS | Design Doc、proposal、delta spec 与实现路径一致 |
| Safety | PASS | `git diff --check` 通过；新增行密钥关键词扫描无命中 |
| Branch | PENDING | 当前分支 `feature/20260618/fix-release-flow-marketplace-identity` 无 upstream，工作区未提交 |

## 执行命令

- `C:\msys64\usr\bin\bash.exe .comet/build-check.sh`
  - 结果：`72 passed in 13.81s`
- `openspec validate "fix-release-flow-marketplace-identity" --strict`
  - 结果：`Change 'fix-release-flow-marketplace-identity' is valid`
- `git diff --check`
  - 结果：exit 0，无输出
- `git diff -U0 HEAD | rg -n "^\+.*(?i)(password|secret|api[_-]?key|private key|begin rsa|begin openssh|token)"`
  - 结果：无新增行命中

## OpenSpec 对照

### release-flow-plugin

- `Marketplace identity 注册`：已由 `.release-flow/projection.yaml` 和模板声明 `identity.codex`、`identity.claude`、`identity.releaseFlowPlugin`。
- `发布插件来源变量声明`：`RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 已纳入 required variables，`github-plan`、`configure-github --dry-run` 和 preflight 输出包含 expected/manual step。
- `Codex marketplace 由发布流程生成`：source branch 删除 `.agents/plugins/marketplace.json`，projection generator 生成发布分支 Codex marketplace。
- `Marketplace identity 漂移检查`：preflight 在 expected tree 和 channel tree 比对前先校验 marketplace identity。

实现抽查依据：

- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:586` `generate_codex_marketplace()`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:821` `apply_projection()`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:828` `required_variable_report()`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:847` `identity_variable_errors()`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:872` `marketplace_identity_errors()`
- `plugins/release-flow/skills/release-flow/scripts/release_flow.py:1011` `preflight_errors()`

### agent-guard-plugin-runtime

- `Installer 使用共享 marketplace identity`：installer 从 `.release-flow/projection.yaml` 读取共享 identity，生成和验证 Codex/Claude catalog root。
- `Source repo 与 repo scope marketplace 边界`：默认 verify scope 只检查 personal；本仓库 source branch 不再要求 Codex repo-local marketplace，显式 repo scope 仍可写入目标项目路径。

实现抽查依据：

- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:123` `read_shared_marketplace_identity()`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:231` `verify_scopes_for()`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:237` catalog root helpers
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:307` `write_marketplace()`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:366` `marketplace_entry_status()`
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py:499` `run_verify()`

## 风险与阻塞

- 工作区仍有未提交变更，包括本 change 实现与此前用户确认的 `standardize-agent-guard-release-flow` 归档结果。
- Comet `verify` 阶段的分支收尾还未完成；需要用户选择保留分支、推送 PR、合并或丢弃。
- 在用户确认分支处理前，不应运行 verify guard 推进到 `archive`。
