## ADDED Requirements

### Requirement: Comet review gate 不改变阶段链
系统 MUST 在不新增 Comet phase（阶段）的前提下支持 build 到 verify 之间的 agent review gate（代理审查门禁）。

#### Scenario: 原始 Comet 流程保持可用
- **WHEN** 用户运行原始 Comet 流程
- **THEN** 系统仍按 `open -> design -> build -> verify -> archive` 阶段链推进

#### Scenario: reviewed flow 进入门禁
- **WHEN** reviewed flow（带审查流程）完成 Comet build 阶段
- **THEN** 系统在启动 Comet verify 前运行跨 agent review 和 Agent Guard gate completion（门禁完成）

### Requirement: Comet review gate 使用 Gate Binding
系统 MUST 使用 Gate Binding（门禁绑定）表达 Comet `before_verify` 门禁，而不是使用 Session Focus Binding（会话焦点绑定）。

#### Scenario: 创建 before_verify 门禁绑定
- **WHEN** reviewed flow 为 Comet change 创建 review gate
- **THEN** 系统使用 `profile_id: comet-agent-review-gate`、`gate_id: before_verify` 和包含 repo、change id、head ref 的 subject key 创建 Gate Binding（门禁绑定）

#### Scenario: 门禁不抢占会话焦点
- **WHEN** reviewed flow 创建或完成 `before_verify` Gate Binding（门禁绑定）
- **THEN** 当前 Session Focus Binding（会话焦点绑定）保持不变

### Requirement: Comet review gate 校验 pass marker
系统 MUST 使用 Agent Guard JSON artifact checks（JSON 产物检查）校验跨 agent review 产出的 `review-pass.json`。

#### Scenario: pass marker 合法
- **WHEN** `review-pass.json` 存在，且 `status` 为 `pass`、`change` 匹配当前 change、`head_ref` 匹配当前 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Agent Guard gate completion（门禁完成）通过，并允许 reviewed flow 启动 `/comet-verify`

#### Scenario: pass marker 缺失
- **WHEN** review report（审查报告）存在但 `review-pass.json` 不存在
- **THEN** Agent Guard gate completion（门禁完成）失败，并且 reviewed flow 不得启动 `/comet-verify`

#### Scenario: pass marker 过期
- **WHEN** `review-pass.json` 的 `head_ref` 不匹配当前 HEAD
- **THEN** Agent Guard gate completion（门禁完成）失败，并提示重新运行跨 agent review

### Requirement: review fail 回到 build 修复
系统 MUST 在跨 agent review 不通过时停在 verify 前，并让用户回 build 修复或重新 review。

#### Scenario: 阻塞发现
- **WHEN** 跨 agent review 报告包含 CRITICAL 或 IMPORTANT findings（发现项）
- **THEN** reviewed flow 不生成 pass marker，不提交通过门禁，并提示回 build 修复

#### Scenario: 修复后重新审查
- **WHEN** 用户修复 blocking findings（阻塞发现）并更新 HEAD
- **THEN** reviewed flow 必须重新运行跨 agent review，并使用新 head ref 创建新的 gate evidence（门禁证据）
