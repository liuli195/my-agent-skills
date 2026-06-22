## MODIFIED Requirements

### Requirement: Comet review gate 通过产物注册层校验 pass marker

系统 MUST 通过 Agent Guard artifacts.yaml 产物注册层引用 cross-agent-review（跨代理审查）默认输出的 `review-pass.json`，并使用 Global Command Guard（全局命令守卫点）的 JSON predicate（JSON 谓词）校验该 pass marker（通过标记）。系统 MUST NOT 要求 cross-agent-review 修改默认输出目录、复制 pass marker 到另一套 evidence 目录，或改变 cross-agent-review 的边界行为。

#### Scenario: 注册 cross-agent-review pass marker

- **WHEN** 用户级 Guard Profile（守卫画像）配置 Comet review gate
- **THEN** `artifacts.yaml` 注册 `cross_agent_review_pass` 产物
- **AND** 该产物路径指向项目内 `.local/cross-agent-review/<change>/<head_ref_short>/review-pass.json`
- **AND** `<change>` 来自 Global Command Guard（全局命令守卫点）的命令捕获值
- **AND** `<head_ref_short>` 来自当前 Git HEAD 的 12 位短值
- **AND** Global Command Guard 通过 `artifact` 或 `artifact_id` 引用该注册产物，而不是直接声明独立 `evidence.path`

#### Scenario: pass marker 合法

- **WHEN** `review-pass.json` 存在于当前 change 和当前短 HEAD 对应目录
- **AND** `status` 为 `pass`、`change` 匹配当前 change、`head_ref` 匹配当前完整 HEAD、`blocking_findings` 为 0、`report` 存在且 `report_hash` 存在
- **THEN** Global Command Guard（全局命令守卫点）允许 Comet build 阶段守卫收尾命令继续执行
