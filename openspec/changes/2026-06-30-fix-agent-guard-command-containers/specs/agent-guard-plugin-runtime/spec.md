## MODIFIED Requirements

### Requirement: Shared guard check evaluator

系统 MUST 将可复用检查能力从 Session Focus（会话焦点）和 Guard Instance（守卫实例）专用路径中抽象出来，使 Global Command Guard（全局命令守卫点）和现有 Guard Point（守卫点）可以共享。

#### Scenario: 复用命令提取与匹配
- **WHEN** Runtime（运行时）处理 PreToolUse
- **THEN** Session Focus permission（会话焦点权限）和 Global Command Guard MUST 使用同一套 command extraction（命令提取）基础能力

#### Scenario: command extraction 识别一层 tool input containers
- **WHEN** PreToolUse payload（载荷）的 command（命令）位于 top-level（顶层）、`tool_input`、`input`、`parameters`、`params`、`args` 或 `arguments`
- **THEN** command extraction（命令提取）MUST 识别字符串 `command` 或 `cmd`
- **AND** unsupported nested values（不支持的嵌套值）MUST 被安全忽略
