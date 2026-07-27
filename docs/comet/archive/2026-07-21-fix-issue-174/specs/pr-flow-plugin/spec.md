## ADDED Requirements

### Requirement: 已安装插件从自身位置执行 PR Flow
PR Flow Plugin（拉取请求流程插件）MUST 为 Pi（编码助手）提供从已安装插件自身位置解析 `pr_flow.py`（PR Flow 脚本）的执行入口。脚本位置 MUST 与目标项目目录分离；目标项目仍由 `--project`（项目参数）解析。

#### Scenario: Pi 在外部目标仓库运行
- **WHEN** Pi（编码助手）在不包含 `plugins/pr-flow`（拉取请求流程源码路径）的目标仓库中从 PR Flow Skill（拉取请求流程技能）入口执行命令
- **THEN** 入口 MUST 调用已安装插件内的 `pr_flow.py`（PR Flow 脚本）
- **THEN** `--project .`（项目参数）MUST 继续指向目标仓库，而不是插件目录

#### Scenario: 恢复命令不依赖源码仓库布局
- **WHEN** PR Flow（拉取请求流程）输出包含 `nextCommand`（下一命令）的可恢复停止状态
- **THEN** 该命令中的脚本位置 MUST 由执行中的 `pr_flow.py`（PR Flow 脚本）自身解析
- **THEN** 用户在目标仓库执行该命令时 MUST NOT 需要存在 `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`（源码仓库脚本路径）

#### Scenario: Codex 与 Claude 保持兼容
- **WHEN** Codex（编码助手）或 Claude（克劳德）从其插件缓存运行 PR Flow（拉取请求流程）
- **THEN** 入口和恢复命令 MUST 指向该已安装版本的脚本
- **THEN** 源码仓库中的文档仍 MAY 展示维护者专用的源码路径示例，且不得要求目标仓库复制该路径
