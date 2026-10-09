## MODIFIED Requirements

### Requirement: 守卫画像来源元数据

系统 MUST 在每个业务 Guard Profile（守卫画像）manifest（清单）中记录来源元数据，并要求 `grill-with-docs-confirmed-notes` 来源具备 confirmed（已确认）状态。系统 MAY 接受明确列入白名单的内置 Guard Profile（守卫画像）模板来源。

#### Scenario: 已确认来源清单

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: grill-with-docs-confirmed-notes`
- **THEN** 该 manifest（清单）同时包含 `source.status: confirmed`

#### Scenario: 内置 Comet review gate 模板来源

- **WHEN** Guard Profile（守卫画像）manifest（清单）使用 `source.kind: built-in-comet-review-gate`
- **THEN** Validator（校验器）接受该来源类型
- **AND** Validator（校验器）继续校验该 Guard Profile（守卫画像）的其他文件和引用
