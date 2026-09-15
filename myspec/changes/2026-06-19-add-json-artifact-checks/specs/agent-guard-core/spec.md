## ADDED Requirements

### Requirement: JSON artifact 内容守卫检查
系统 MUST 支持 Guard Point（守卫点）声明通用 `json_artifact` check，用于读取 profile-owned JSON artifact（画像拥有的 JSON 产物）并校验其内容。

#### Scenario: JSON 内容检查通过
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在、JSON 可解析，且所有声明谓词均通过
- **THEN** Runtime（运行时）把该 check 视为通过，并继续评估同一 Guard Point 的后续检查

#### Scenario: JSON 内容检查失败
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在且 JSON 可解析，但字段值不满足声明谓词
- **THEN** Runtime（运行时）保持当前 Guard Instance（守卫实例）状态不变，并返回 `guard_failed`
- **THEN** audit（审计）记录失败的 artifact id、field path（字段路径）、predicate（谓词）、expected（期望值）和 actual（实际值）

#### Scenario: JSON 文件无法解析
- **WHEN** Guard Point 声明 `json_artifact` check，目标 artifact 存在但不是合法 JSON
- **THEN** Runtime（运行时）返回 `guard_failed`
- **THEN** audit（审计）记录 `invalid_json_artifact` 和目标 artifact id

### Requirement: JSON artifact 谓词集合
系统 MUST 为 `json_artifact` check 支持受限、声明式、可验证的谓词集合，并拒绝执行任意脚本或表达式。

#### Scenario: 字段存在检查
- **WHEN** check 声明 `predicate: exists` 和 `field`
- **THEN** Runtime（运行时）要求该字段路径在 JSON 对象中存在

#### Scenario: 字段等值检查
- **WHEN** check 声明 `predicate: equals` 和 `value`
- **THEN** Runtime（运行时）要求字段路径的实际值等于声明值

#### Scenario: 数字比较检查
- **WHEN** check 声明 `predicate: number_lte` 或 `predicate: number_gte`
- **THEN** Runtime（运行时）要求字段路径的实际值和声明值均为数字，并按对应比较规则判断

#### Scenario: 数组元素检查
- **WHEN** check 声明 `predicate: array_none` 或 `predicate: array_all`
- **THEN** Runtime（运行时）要求目标字段是数组，并按元素子谓词判断每个数组元素

### Requirement: JSON artifact check 声明校验
系统 MUST 在 Guard Profile（守卫画像）校验阶段拒绝无效或不支持的 `json_artifact` check 声明。

#### Scenario: 未知谓词
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 且 `predicate` 不在支持列表内
- **THEN** validator（校验器）报告清晰错误，并拒绝该画像作为可初始化画像

#### Scenario: 缺少 artifact 引用
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 但未声明 `artifact` 或 `artifact_id`
- **THEN** validator（校验器）报告缺少 artifact 引用

#### Scenario: 引用不存在的 artifact
- **WHEN** Guard Profile（守卫画像）包含 `json_artifact` check 且引用的 artifact id 不存在于 `artifacts.yaml`
- **THEN** validator（校验器）报告该引用无效
