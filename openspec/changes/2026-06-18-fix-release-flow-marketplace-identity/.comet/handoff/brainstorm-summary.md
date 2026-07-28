# Brainstorm Summary

- Change: fix-release-flow-marketplace-identity
- Date: 2026-06-18

## 确认的技术方案

采用方案 C：扩展 `.release-flow/projection.yaml` 的语义。`config.yaml` 只保存仓库级 release-flow 通用配置，project-specific marketplace identity（项目市场身份）归属 projection。

## 候选方案

### 方案 A：identity 放入 `.release-flow/config.yaml` 的 `marketplace.identity`

- release-flow 已经强依赖 `read_config()`，所有核心命令都会读取 config。
- 适合保存非敏感 identity 字段：Codex/Claude marketplace name/display/owner、release-flow plugin repository/ref。
- projection 继续只描述变量和 JSON transform，不承担事实源职责。

### 方案 B：新增 `.release-flow/identity.yaml`

- 身份注册表更独立，但会新增一个配置文件和一套读取/校验入口。
- 对当前范围来说文件数和迁移成本更高。

### 方案 C：扩展 `.release-flow/projection.yaml` 的语义

- 按领域归属，projection 表达“本项目如何投影成 marketplace 发布形态”。
- 可同时包含 identity、required variables 和 transforms/generators。
- installer 和 release-flow 读取同一 projection identity。

## 关键取舍与风险

- 用户明确选择方案 C。关键原则：`config.yaml` 是仓库级发布通用配置，不耦合项目 marketplace 逻辑；项目配置都在 `projection.yaml`。
- 风险：projection 语义变宽，需要保持结构清晰。缓解：把字段分区为 `identity`、`variables`、`transforms`/`generators`，并用 parser 校验边界。

## 测试策略

- release-flow CLI 测试覆盖 identity 缺失、变量缺失、生成 marketplace、identity 漂移。
- installer 测试覆盖默认 catalog root 读取 identity、repo Codex marketplace 缺失不影响 package verification。
- E2E 覆盖 source branch 无 Codex marketplace，ci-publish dry-run 生成 expected marketplace tree。

## Spec Patch

已回写 OpenSpec 支撑设计和 release-flow delta spec：identity 必须位于 `.release-flow/projection.yaml`，不得放入 `.release-flow/config.yaml`。
