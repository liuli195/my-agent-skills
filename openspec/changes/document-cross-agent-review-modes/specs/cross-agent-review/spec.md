## ADDED Requirements

### Requirement: review（审查）模式选择

系统 MUST 支持默认收敛模式和显式无尽模式。模式只影响调用方准备输入和 reviewer prompt（审查提示词）的复审范围，不得改变 CLI（命令行接口）参数、输出目录、pass marker（通过标记）或脚本行为。

#### Scenario: 默认收敛模式

- **WHEN** 调用方没有明确要求无尽模式
- **THEN** cross-agent-review（跨代理审查）MUST 使用收敛模式
- **AND** 首轮 review（审查）MUST 覆盖完整 review subject（审查对象）
- **AND** 修复 CRITICAL（严重阻断）或 IMPORTANT（重要阻断）findings（发现项）后重新 review（审查）时，调用方 MAY 将范围收窄到上一轮阻断问题、对应修复、变更路径和直接受影响上下文
- **AND** 如果无法安全判断影响范围，调用方 MUST 扩大到完整 review subject（审查对象）

#### Scenario: 显式无尽模式

- **WHEN** 用户或调用方明确要求无尽模式、每轮完整复查、不要收窄范围或等价表达
- **THEN** cross-agent-review（跨代理审查）MUST 使用无尽模式
- **AND** 每轮 review（审查）MUST 覆盖完整 review subject（审查对象）和必要上下文
- **AND** 不得因为上一轮 findings（发现项）已被修复而收窄复审范围

#### Scenario: 模式不改变脚本契约

- **WHEN** 调用方选择收敛模式或无尽模式
- **THEN** CLI（命令行接口）参数和 review output（审查输出）契约 MUST 保持不变
- **AND** 模式选择 MUST 通过调用方准备的上下文和 reviewer prompt（审查提示词）表达
