---
comet_change: fix-release-flow-marketplace-identity
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-18-fix-release-flow-marketplace-identity
status: final
---

# Release-Flow Marketplace Identity Design

## 背景

当前 release-flow 已经用 `.release-flow/config.yaml` 描述通用发布流程，用 `.release-flow/projection.yaml` 描述项目如何投影到 `marketplace` 发布分支。但 marketplace identity（市场身份）仍散落在 repo-local marketplace 文件、projection 变量、workflow 模板和 Agent Guard installer 默认值里。

这导致两个问题：

- `main` 分支保存 `.agents/plugins/marketplace.json` 时，Codex Desktop 会把当前仓库识别为本地 marketplace，和正式订阅的 `my-agent-skills-marketplace` 重复。
- workflow 隐式依赖 `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF`，但 setup、GitHub 配置方案和 preflight 没有统一声明和检查。

本设计修 #38、#39、#40：把 marketplace identity 收敛到 project projection（项目投影）中，让发布生成、发布检查和 installer 使用同一事实源。

## 设计原则

`config.yaml` 只保存仓库级 release-flow 通用配置：

- source ref
- channel branch
- workflow file
- records directory
- GitHub Rulesets / permissions 期望
- manifest version files

`projection.yaml` 保存项目级投影配置：

- marketplace identity
- required GitHub Actions Variables
- source branch 到 marketplace branch 的 transforms/generators

这个边界符合领域语言：`config.yaml` 描述“发布流程怎么跑”，`projection.yaml` 描述“这个项目发布成什么样”。

## Projection Schema

扩展 `.release-flow/projection.yaml`，保持 `version`、`variables`、`transforms` 兼容，新增 `identity` 和可选 `generators`：

```yaml
version: 1

identity:
  codex:
    marketplaceName: my-agent-skills-marketplace
    displayName: My Agent Skills Marketplace
  claude:
    marketplaceName: my-agent-skills-marketplace
    ownerName: My Agent Skills Marketplace
  releaseFlowPlugin:
    repositoryVariable: RELEASE_FLOW_PLUGIN_REPOSITORY
    refVariable: RELEASE_FLOW_PLUGIN_REF

variables:
  RELEASE_FLOW_PLUGIN_REPOSITORY:
    source: github-actions-variable
    required: true
    sensitive: false
    description: GitHub repository used by workflow checkout for release-flow plugin
  RELEASE_FLOW_PLUGIN_REF:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Git ref used by workflow checkout for release-flow plugin
  CODEX_MARKETPLACE_CATALOG_NAME:
    source: github-actions-variable
    required: true
    sensitive: false
    description: Codex marketplace catalog name for the latest channel
    expected: identity.codex.marketplaceName
```

`identity` 保存非敏感期望值和变量引用。`variables` 仍声明 GitHub Actions Variables 是否 required、sensitive 和描述。对 marketplace name 这类值，projection 可以用 `expected` 绑定到 identity 字段，让 preflight 能检查变量快照和 identity 是否一致。

## Data Flow

```text
.release-flow/projection.yaml
  identity
  variables
  transforms/generators
        |
        +--> github-plan / configure-github --dry-run
        |      输出 required Actions Variables 和手动设置说明
        |
        +--> preflight
        |      校验变量存在、变量值符合 identity、channel tree 没有未声明差异
        |
        +--> ci-publish / project
        |      生成或修改 marketplace catalog
        |
        +--> Agent Guard installer
               生成/验证 marketplace catalog root 和 entry
```

release-flow 不再从 `.agents/plugins/marketplace.json` 读取正式 marketplace identity。该文件变成发布产物，而不是 source branch 的事实源。

## Marketplace Generation

现有 `json-env` transform 只会修改已有 JSON 文件。#38 要求 source branch 可以没有 `.agents/plugins/marketplace.json`，所以需要增加生成能力。

推荐在 projection 中引入 `generators`，用于声明目标文件可从模板生成：

```yaml
generators:
  - path: .agents/plugins/marketplace.json
    type: codex-marketplace
    identity: codex
    plugins:
      - agent-guard
      - release-flow
```

生成后的 JSON 再允许 `transforms` 做字段覆盖。这样保留已有 transform 模型，同时让“源分支无文件，发布分支有文件”成为明确声明的投影行为。

Claude marketplace 是否继续保留 source 文件由实现阶段按兼容性处理；但 Codex marketplace 必须不再作为 main 的持久 repo-local marketplace 文件。

## Preflight Checks

`preflight` 增加三类检查：

1. Projection identity 结构完整  
   缺少 `identity.codex.marketplaceName`、`identity.codex.displayName`、`identity.claude.marketplaceName`、`identity.claude.ownerName`、`releaseFlowPlugin.repositoryVariable` 或 `releaseFlowPlugin.refVariable` 时失败。

2. Required variables 完整且可解释  
   `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF` 必须在 projection variables 中声明为 required。变量缺失时输出变量名、用途和手动设置步骤。

3. Identity drift（身份漂移）  
   传入的 GitHub Actions Variables 快照、生成的 expected tree、channel tree 中的 marketplace name/display/owner 必须和 projection identity 一致。旧名残留或未声明差异阻断发布。

首版仍不调用真实 GitHub Settings API，也不声称已回读验证 Rulesets 或 workflow permissions。

## Installer Integration

Agent Guard installer 读取共享 projection identity：

- 默认 Codex catalog root 使用 `identity.codex.marketplaceName` 和 `identity.codex.displayName`。
- 默认 Claude catalog root 使用 `identity.claude.marketplaceName` 和 `identity.claude.ownerName`。
- `marketplace_entry_status()` 验证 catalog root identity 和 plugin entry。

本仓库 source branch 缺少 `.agents/plugins/marketplace.json` 不代表 plugin package 不完整。只有用户显式以 repo scope 指向某个目标项目 marketplace 路径时，installer 才写入或验证该 repo marketplace。

## Implementation Notes

建议新增小型数据结构，而不是在各命令里散读 dict：

- `ProjectionIdentity`
- `ProjectionVariable`
- `ProjectionGenerator`
- `Projection`

核心 helper：

- `read_projection()` 解析并校验 identity、variables、transforms、generators。
- `required_github_variables()` 从 variables 读取 required 项。
- `identity_variable_errors()` 校验 expected 变量值。
- `apply_projection()` 先运行 generators，再运行 transforms。
- `marketplace_identity_errors()` 校验生成树或 channel tree 的 marketplace identity。

Agent Guard installer 可以优先从 repo root 的 `.release-flow/projection.yaml` 读取 identity；读取失败时使用当前正式默认值，但 verify 时应报告无法校验共享 identity。

## Test Strategy

测试先行：

- release-flow parser 测试：projection identity 缺字段时报错。
- `github-plan` / `configure-github --dry-run` 测试：输出 `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF` 及说明。
- preflight 测试：变量缺失、变量值与 identity 不一致、channel tree 旧名残留时失败。
- projection 测试：source branch 无 `.agents/plugins/marketplace.json`，apply/ci-publish dry-run 能生成 Codex marketplace。
- installer 测试：catalog root 从 projection identity 读取；本仓库 Codex repo marketplace 缺失不影响 package verification。
- 回归命令：`python -m pytest tests/test_release_flow_plugin_package.py tests/test_release_flow_cli.py tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_installer.py -q`

## Risks

- Projection 语义变宽后容易变成杂物箱。  
  缓解：只允许 `identity`、`variables`、`transforms`、`generators` 四个投影域，各域由 parser 明确校验。

- Installer 读取 repo projection 可能在目标项目不存在 release-flow 配置时失败。  
  缓解：install/dry-run 可用默认 identity，verify 模式报告 shared identity 状态；目标项目显式 repo scope 仍由传入路径决定。

- 移除 Codex repo-local marketplace 会影响旧测试。  
  缓解：更新 package tests，把 Codex marketplace 从 source artifact 改为 release projection artifact。

## Spec Patch

已回写 OpenSpec delta spec：`release-flow-plugin` 明确 identity 必须位于 `.release-flow/projection.yaml`，不得放入 `.release-flow/config.yaml`。
