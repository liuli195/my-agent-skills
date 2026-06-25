## MODIFIED Requirements

### Requirement: 守卫画像来源元数据

系统 MUST 在每个业务 Guard Profile（守卫画像）manifest（清单）中记录来源元数据，并要求 `grill-with-docs-confirmed-notes` 来源具备 confirmed（已确认）状态。系统 MAY 接受明确列入白名单的通用内置 Guard Profile（守卫画像）模板来源，但 MUST NOT 为具体业务 workflow（工作流）保留内置来源白名单。

#### Scenario: 已确认来源清单

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: grill-with-docs-confirmed-notes`
- **THEN** 该 manifest（清单）同时包含 `source.status: confirmed`

#### Scenario: 通用内置模板来源

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用通用内置模板来源，例如 `built-in-minimal-sample`
- **THEN** Validator（校验器）MAY 接受该来源类型
- **AND** Validator（校验器）继续校验该 Guard Profile（守卫画像）的其他文件和引用

#### Scenario: 业务专用内置来源不再被接受

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用业务 workflow（工作流）专用来源，例如 `source.kind: built-in-comet-review-gate`
- **THEN** Validator（校验器）MUST 拒绝该来源类型
- **AND** Agent Guard Plugin（代理守卫插件）不得通过该来源类型表达 Comet（流程）业务配置

#### Scenario: 模板记录保持未确认

- **WHEN** 系统创建 `confirmed-notes.yaml` 模板
- **THEN** 模板状态保持为 `needs_confirmation`，直到调研流程明确确认它
