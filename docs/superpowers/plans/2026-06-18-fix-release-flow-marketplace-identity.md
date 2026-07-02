---
change: fix-release-flow-marketplace-identity
design-doc: docs/superpowers/specs/2026-06-18-fix-release-flow-marketplace-identity-design.md
base-ref: b428c918259fcf9ac25abbe99dad8b79c5eca4cd
archived-with: 2026-06-18-fix-release-flow-marketplace-identity
---

# Fix Release Flow Marketplace Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 修复 #38、#39、#40：`main` 不再持久保存 Codex repo-local marketplace catalog；release-flow 从 `.release-flow/projection.yaml` 生成发布分支 marketplace identity；GitHub Actions Variables 和 Agent Guard installer 都读取同一 project projection。

**Architecture:** `.release-flow/config.yaml` 只保存仓库级发布流程配置；`.release-flow/projection.yaml` 保存项目级 identity、variables、generators、transforms。`release_flow.py` 负责解析 projection、生成发布树、preflight 校验和 GitHub 配置说明；Agent Guard installer 只消费 projection identity，不另建默认事实源。

**Tech Stack:** Python CLI（`argparse`）、PyYAML、pytest、OpenSpec、GitHub Actions workflow template。

archived-with: 2026-06-18-fix-release-flow-marketplace-identity
---

## Current State

- `plugins/release-flow/skills/release-flow/scripts/release_flow.py` 当前只有 `ProjectionVariable`、`ProjectionTransform`、`Projection`，`read_projection()` 只解析 `variables/transforms`。
- `run_project()` 目前直接循环 transform；`ci-publish` dry-run 和 preflight 通过 `apply_projection()` 复用同一逻辑。
- `.release-flow/projection.yaml` 和 release-flow template 仍把 Codex/Claude marketplace name 作为普通变量，并要求 `.agents/plugins/marketplace.json` 已存在。
- `.github/workflows/release.yml` 已使用 `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` checkout 插件，但 projection、`github-plan`、`configure-github --dry-run` 和 preflight 还没有统一声明/检查它们。
- `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py` 的 `codex_catalog_root()`、`claude_catalog_root()` 使用硬编码 marketplace identity。
- `tests/test_agent_guard_plugin_package.py` 当前把 `.agents/plugins/marketplace.json` 当作 source branch 必需文件，需要改成 release projection artifact。

## Implementation Rules

- 不把任何项目 identity 放入 `.release-flow/config.yaml`。
- 先写失败测试，再实现。
- 保留现有 CLI 退出码习惯：配置/校验问题返回 `1`，缺少明确授权返回 `2`。
- 删除 `.agents/plugins/marketplace.json` 只限 Codex repo-local marketplace source 文件；`.claude-plugin/marketplace.json` 本轮保留，除非测试证明必须同时生成。
- 不提交、不推送、不切分支；这些动作需要用户另行授权。

## Phase 1: Tests First

- [x] 1.1 在 `tests/test_release_flow_cli.py` 添加 projection schema 测试：
  - `read_projection` 经 CLI `validate` 接受 `identity`、`variables.expected`、`generators`。
  - 缺 `identity.codex.marketplaceName`、`identity.codex.displayName`、`identity.claude.marketplaceName`、`identity.claude.ownerName`、`identity.releaseFlowPlugin.repositoryVariable`、`identity.releaseFlowPlugin.refVariable` 时失败。
  - `RELEASE_FLOW_PLUGIN_REPOSITORY` 和 `RELEASE_FLOW_PLUGIN_REF` 未声明为 required variable 时失败。
- [x] 1.2 在 `tests/test_release_flow_cli.py` 添加 generator 测试：
  - fixture project 不创建 `.agents/plugins/marketplace.json`。
  - projection 声明 `generators: [{path: .agents/plugins/marketplace.json, type: codex-marketplace, identity: codex, plugins: [agent-guard, release-flow]}]`。
  - `project --vars-file ...` 后生成 Codex catalog，包含 projection identity 和两个 plugin entry。
- [x] 1.3 扩展 `tests/test_release_flow_cli.py::test_github_plan_outputs_expected_settings` 和 `test_configure_github_dry_run_prints_manual_steps`：
  - 输出必须包含 `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF`。
  - 输出显示变量说明和手动设置步骤，至少包含变量名和 `description`。
- [x] 1.4 添加 preflight 测试：
  - 缺 required variable 时输出 `missing_required_variable: NAME`，并在 `preflight-report.json` 的 `variables.required` 中记录 description/manualStep。
  - `variables.NAME.expected` 绑定到 `identity.*` 时，vars snapshot 值不一致触发 `identity_variable_mismatch: NAME`。
  - channel tree 有旧 marketplace name/display/owner 时触发 identity drift 错误，而不是只报笼统 unmanaged diff。
- [x] 1.5 扩展 `test_ci_publish_dry_run_applies_projection_without_remote_writes`：
  - source branch 缺 `.agents/plugins/marketplace.json` 时，dry-run projected tree 仍生成 `.agents/plugins/marketplace.json`。
- [x] 1.6 更新 `tests/test_agent_guard_plugin_package.py`：
  - 删除 Codex repo marketplace source 文件必需断言。
  - 保留 Claude marketplace source 文件断言。
  - 增加 release-flow projection 负责 Codex marketplace generation 的断言。
- [x] 1.7 更新 `tests/test_agent_guard_plugin_installer.py`：
  - installer 从 repo root `.release-flow/projection.yaml` 读取 Codex/Claude identity。
  - 默认 verify 不因本仓库缺 `.agents/plugins/marketplace.json` 失败；只有显式 `--scope repo` 或 `--scope all` 才验证 repo marketplace path。
  - `marketplace_entry_status()` 对 catalog root identity 不一致时返回明确错误。

## Phase 2: Extend Projection Model

- [x] 2.1 修改 `plugins/release-flow/skills/release-flow/scripts/release_flow.py` dataclass：
  - 新增 `ProjectionCodexIdentity(marketplace_name, display_name)`。
  - 新增 `ProjectionClaudeIdentity(marketplace_name, owner_name)`。
  - 新增 `ProjectionReleaseFlowPluginIdentity(repository_variable, ref_variable)`。
  - 新增 `ProjectionIdentity(codex, claude, release_flow_plugin)`。
  - 新增 `ProjectionGenerator(path, type, identity, plugins)`。
  - `Projection` 新增 `identity` 和 `generators` 字段。
- [x] 2.2 修改 `read_projection(project)`：
  - 解析 `identity.codex.marketplaceName`、`identity.codex.displayName`、`identity.claude.marketplaceName`、`identity.claude.ownerName`。
  - 解析 `identity.releaseFlowPlugin.repositoryVariable`、`identity.releaseFlowPlugin.refVariable`。
  - 解析 `variables.*.expected`，允许值为 `identity.codex.marketplaceName` 这类 projection reference。
  - 解析 `generators`，验证 path 在 project 内，`type` 是支持值，`identity` 是 `codex`，`plugins` 是字符串列表。
- [x] 2.3 修改 `projection_errors(projection)`：
  - 校验 `identity.releaseFlowPlugin.repositoryVariable/refVariable` 指向的 variables 存在、source 是 `github-actions-variable`、`required: true`。
  - 校验 `variables.*.expected` 只能引用已知 identity 字段。
  - 校验 generator path/type/identity/plugins。
  - 保持现有 `projection_variable_value_forbidden`，继续禁止在 projection 存真实变量值。
- [x] 2.4 增加 helper：
  - `projection_identity_value(projection, reference: str) -> str`
  - `required_github_variable_details(projection) -> list[ProjectionVariable]`
  - `expected_variable_value(projection, variable) -> str | None`

## Phase 3: Generate Marketplace Catalogs

- [x] 3.1 在 `release_flow.py` 增加 generator helper：
  - `codex_marketplace_entry(plugin_name: str) -> dict`
  - `generate_codex_marketplace(projection, generator) -> dict`
  - `apply_projection_generator(project, projection, generator) -> None`
- [x] 3.2 Codex generator 输出结构：
  - root `name` 来自 `identity.codex.marketplaceName`。
  - root `interface.displayName` 来自 `identity.codex.displayName`。
  - `agent-guard` entry 保持现有 source/policy/category。
  - `release-flow` entry 保持现有 source/policy/category。
  - 未知 plugin name 失败：`projection_generator_plugin_unknown: NAME`。
- [x] 3.3 修改 `apply_projection()`：
  - 先运行 generators，确保缺失目标文件可生成。
  - 再运行 transforms，允许 variables 覆盖生成结果。
  - 修改 `run_project()` 直接调用 `apply_projection()`，不再绕过 generators。
- [x] 3.4 更新 `.release-flow/projection.yaml`：
  - 新增 `identity`。
  - 新增 required variables：`RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF`。
  - 给 marketplace variables 增加 `expected: identity.*`。
  - 新增 Codex marketplace generator。
  - 保留 Claude transform。
- [x] 3.5 同步更新 `plugins/release-flow/skills/release-flow/assets/templates/release-flow/projection.yaml`。
- [x] 3.6 删除 source branch 的 `.agents/plugins/marketplace.json`。

## Phase 4: GitHub Plan, Workflow Variables, And Preflight

- [x] 4.1 修改 `run_github_plan()`：
  - `actions_variables` 输出 required variables 与非 required variables。
  - 每个变量输出 name、required、description、expected（如果有）。
  - 明确包含 `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF`。
- [x] 4.2 修改 `run_configure_github --dry-run`：
  - 手动步骤中列出变量名、用途、是否 required。
  - 对 required 变量输出 `Set GitHub Actions Variable NAME`。
- [x] 4.3 修改 `.github/workflows/release.yml` 和 template：
  - `Write release variables` step 继续写 marketplace variables。
  - 不把 `RELEASE_FLOW_PLUGIN_REPOSITORY/REF` 写入 release-vars.json，除非 projection transform/generator 需要它们；它们只用于 checkout 和 preflight required variable 说明。
- [x] 4.4 修改 `preflight_errors()`：
  - `missing_required_variable` 继续阻断。
  - report 增加 `variables.required`，记录 `name`、`description`、`expected`、`manualStep`、`present`。
  - 对 `expected` 引用做值校验，错误格式：`identity_variable_mismatch: NAME`。
  - 在 channel drift 前生成 expected tree 时运行 generators。
- [x] 4.5 增加 `marketplace_identity_errors(root, projection)`：
  - 检查 `.agents/plugins/marketplace.json` 的 `/name` 和 `/interface/displayName`。
  - 检查 `.claude-plugin/marketplace.json` 的 `/name` 和 `/owner/name`。
  - preflight channel tree 存在时，对 expected tree 和 channel tree 都跑 identity check；错误格式包含 path 和字段名。

## Phase 5: Agent Guard Installer Integration

- [x] 5.1 修改 `plugins/agent-guard/skills/agent-guard/scripts/install_agent_guard_plugin.py`：
  - 新增轻量 `MarketplaceIdentity` dataclass。
  - 新增 `read_shared_marketplace_identity(root: Path) -> tuple[MarketplaceIdentity, list[str]]`。
  - 优先读 `repo_root()/.release-flow/projection.yaml`；如果 `PyYAML` 不可用或 projection 不存在，使用当前默认 identity 并在 verify 输出 warning。
- [x] 5.2 修改 catalog root helper：
  - `codex_catalog_root(identity)` 使用 `identity.codex.marketplaceName/displayName`。
  - `claude_catalog_root(identity)` 使用 `identity.claude.marketplaceName/ownerName`。
  - `catalog_root(target, identity)` 贯穿 `read_marketplace()`、`write_marketplace()`、`marketplace_entry_status()`。
- [x] 5.3 修改 verify 行为：
  - `run_verify()` 默认 scope 只检查 personal marketplace，避免本仓库 source branch 缺 Codex repo marketplace 被判失败。
  - 用户显式 `--scope repo` 或 `--scope all` 时，继续验证传入 repo marketplace path。
  - 输出 shared identity 状态：`shared_identity: loaded|defaulted`。
- [x] 5.4 修改 `marketplace_entry_status()`：
  - 校验 catalog root identity。
  - entry 不匹配继续返回 `invalid_marketplace_entry`。
  - root identity 不匹配返回 `invalid_marketplace_identity: PATH FIELD`。

## Phase 6: Docs And Specs Alignment

- [x] 6.1 更新 release-flow 相关说明文档，说明：
  - `config.yaml` 是发布通用配置。
  - `projection.yaml` 是 project projection 和 marketplace identity 来源。
  - Codex marketplace catalog 是 release projection artifact，不在 `main` 持久保存。
- [x] 6.2 更新 Agent Guard installer 说明，说明 shared identity 来源和 repo scope 验证边界。
- [x] 6.3 不修改已确认的 OpenSpec 语义，除非实现中发现必须补充 delta spec；如补充，重新跑 strict validation。

## Phase 7: Verification

- [x] 7.1 运行 focused tests：
  - `python -m pytest tests/test_release_flow_cli.py -q`
  - `python -m pytest tests/test_agent_guard_plugin_package.py tests/test_agent_guard_plugin_installer.py -q`
- [x] 7.2 运行 package tests：
  - `python -m pytest tests/test_release_flow_plugin_package.py tests/test_agent_guard_plugin_package.py -q`
- [x] 7.3 运行 OpenSpec validation：
  - `openspec validate "fix-release-flow-marketplace-identity" --strict`
- [x] 7.4 运行 workspace hygiene：
  - `git diff --check`
  - `git status --short`
- [x] 7.5 如果本机 `python` 不是项目期望解释器，改用可用的 repo Python 入口，并在验证结果中说明。

## Expected Result

- `main` 分支没有 `.agents/plugins/marketplace.json`。
- `release-flow project` 和 `ci-publish --dry-run` 能从 projection 生成 `.agents/plugins/marketplace.json`。
- `github-plan` 和 `configure-github --dry-run` 明确列出 `RELEASE_FLOW_PLUGIN_REPOSITORY`、`RELEASE_FLOW_PLUGIN_REF`。
- `preflight` 能阻断 missing variable、identity variable mismatch、channel marketplace identity drift。
- Agent Guard installer 的 marketplace root identity 来自 `.release-flow/projection.yaml`，且默认 verify 不把 source branch 缺 Codex repo marketplace 当作包缺失。
