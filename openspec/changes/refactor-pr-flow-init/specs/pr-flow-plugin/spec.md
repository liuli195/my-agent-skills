## MODIFIED Requirements

### Requirement: Repository PR Flow configuration
系统 MUST 使用 `.pr-flow/config.yaml` 保存仓库共享 PR Flow 配置，并将该文件纳入 Git（版本管理）。

#### Scenario: Agent-driven init prepares confirmed configuration
- **WHEN** 用户通过 `pr-flow-init` Skill（初始化技能）启用 PR Flow（拉取请求流程）
- **THEN** agent（代理）MUST 通过对话收集运行配置和 GitHub（代码托管平台）配置意图
- **THEN** agent（代理）MUST 展示 `.pr-flow/config.yaml` 草案、校验结果和配置建议
- **THEN** agent（代理）MUST 在用户明确确认后才写入本地文件

#### Scenario: Init creates local configuration from confirmed input
- **WHEN** 用户确认 repo init（仓库初始化）配置
- **THEN** 系统 MUST 创建 `.pr-flow/config.yaml`
- **THEN** 系统 MUST 创建 PR body template（拉取请求正文模板）
- **THEN** 系统 MUST 创建 `.pr-flow/.gitignore`，忽略本地运行记录和最后状态
- **THEN** init（初始化）脚本 MAY 写入已确认的本地配置文件
- **THEN** init（初始化）脚本 MUST NOT 进行终端交互式问答
- **THEN** init（初始化）脚本 MUST 在任何本地写入前要求已确认配置输入
- **THEN** init（初始化）脚本 MUST NOT silently write generated defaults when only `--base-branch`（目标分支参数） or no config input is provided

#### Scenario: Init does not write GitHub settings
- **WHEN** 用户运行 repo init（仓库初始化）
- **THEN** 系统 MUST 输出 GitHub Rulesets（GitHub 规则集）建议配置
- **THEN** 系统 MUST NOT 调用 `gh api` 或其他 GitHub API（接口）写入远端仓库设置
- **THEN** 系统 MUST NOT 声称已回读验证 GitHub Rulesets（GitHub 规则集）

#### Scenario: Defaults and branch overrides
- **WHEN** `.pr-flow/config.yaml` 声明配置
- **THEN** 配置 MUST 支持 `defaults` 默认规则
- **THEN** 配置 MUST 支持 `branches` 分支覆盖
- **THEN** 分支覆盖 MUST 只覆盖该目标分支需要改变的字段

#### Scenario: Setup suggestions are not runtime commands
- **WHEN** `.pr-flow/config.yaml` 包含 `setup.github`（GitHub 配置建议）
- **THEN** complete、cleanup、hotfix、tweak 和 diagnose（收尾、清理、热修复、小改、诊断）命令 MUST NOT 把 `setup.github` 作为运行配置消费
- **THEN** `setup.github` MUST 只作为 agent（代理）继续人工配置 GitHub（代码托管平台）的建议输入

## ADDED Requirements

### Requirement: PR Flow init validates confirmed configuration
系统 MUST 提供只读配置校验能力，用于校验 `pr-flow-init` Skill（初始化技能）生成的配置草案。

#### Scenario: Validate reads only provided config
- **WHEN** agent（代理）调用 `pr_flow.py validate --config <path>`
- **THEN** validate（校验）MUST 只读取 `<path>` 指向的配置文件
- **THEN** validate（校验）MUST NOT 写入 `.pr-flow/config.yaml`
- **THEN** validate（校验）MUST NOT 调用 GitHub API（GitHub 接口）
- **THEN** validate（校验）MUST NOT 执行 `diagnose`、`complete`、`cleanup`、`hotfix` 或 `tweak`（诊断、收尾、清理、热修复、小改）

#### Scenario: Validate reports structured results
- **WHEN** validate（校验）发现配置问题
- **THEN** validate（校验）MUST 输出 error（错误）、warning（警告）或 setup suggestion（配置建议）
- **THEN** error（错误）MUST 表示配置本身不可用
- **THEN** warning（警告）MUST 表示配置可写入但存在流程风险
- **THEN** setup suggestion（配置建议）MUST 表示需要用户或 agent（代理）另行处理的 GitHub（代码托管平台）或环境配置

#### Scenario: Validation errors block init writes
- **WHEN** init（初始化）准备写入已确认配置
- **AND** validate（校验）对该配置输出一个或多个 error（错误）
- **THEN** init（初始化）MUST stop without writing `.pr-flow/config.yaml`、PR body template（拉取请求正文模板）或 `.pr-flow/.gitignore`
- **THEN** warning（警告）和 setup suggestion（配置建议）MAY be shown before final confirmation, but MUST NOT block writing by themselves

#### Scenario: Validate checks hotfix dependencies
- **WHEN** 任一 `branches.<branch>.allowHotfixPush` 为 `true`
- **THEN** validate（校验）MUST 要求存在 `authorization.phraseHashAlgorithm: md5`
- **THEN** validate（校验）MUST 要求存在非空 `authorization.phraseHash`
- **THEN** validate（校验）MUST 要求存在非空 `hotfix.verifyCommand`
- **THEN** validate（校验）MUST 要求该分支存在非空 `remote`
- **THEN** validate（校验）MUST 输出 Rulesets bypass（规则集绕过权限）配置建议

#### Scenario: Validate checks review gate dependencies
- **WHEN** `reviewGate.mode` 是 `github` 或 `dual`
- **THEN** validate（校验）MUST 输出 required review（必需审查）远端配置建议
- **WHEN** `reviewGate.mode` 是 `local` 或 `dual`
- **THEN** validate（校验）MUST 要求存在非空 `reviewGate.evidencePath`
- **THEN** validate（校验）MUST 输出 review-pass.json（审查通过文件）字段契约建议

#### Scenario: Validate checks GitHub setup dependencies
- **WHEN** 配置声明 required checks（必需检查）意图
- **THEN** validate（校验）MUST 输出 GitHub Rulesets（GitHub 规则集）配置建议
- **WHEN** 配置声明 merge strategy（合并方式）
- **THEN** validate（校验）MUST 输出对应 merge method（合并方式）需要在 GitHub（代码托管平台）启用的建议
- **WHEN** 配置启用 auto-delete head branch（自动删除源分支）意图
- **THEN** validate（校验）MUST 输出 cleanup（清理）职责重叠 warning（警告）

#### Scenario: Validate preserves verification mode boundaries
- **WHEN** validate（校验）读取 review gate evidence（审查门禁证据）路径或 setup.github（GitHub 配置建议）
- **THEN** validate（校验）MUST NOT 推断 full verify（完整验证）已经运行
- **THEN** validate（校验）MUST 保持 full verify（完整验证）仅作为 hotfix.verifyCommand（热修复验证命令）或 PR CI（拉取请求持续集成）建议的显式配置

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Skill entrypoint delegates detail to references
- **WHEN** agent（代理）加载 `pr-flow-init` Skill（初始化技能）
- **THEN** Skill（技能）入口 MUST 声明 hard boundaries（硬边界）、closed loop（闭环）、required flow（必需流程）和 output（输出）
- **THEN** Skill（技能）入口 MUST 指向 `references/questionnaire.md`（问答模板）、`references/config-draft.md`（配置草案规则）和 `references/validation.md`（校验规则）
- **THEN** Skill（技能）入口 MUST NOT 内联完整问答细节

#### Scenario: Questionnaire is fixed
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** agent（代理）MUST 先读取 `references/questionnaire.md`（问答模板）
- **THEN** questionnaire（问答模板）MUST 定义固定问题、固定选项、选择后果和跳转规则
- **THEN** agent（代理）MUST NOT 临场编造初始化问题或跳过最终写入确认
- **THEN** 用户沉默 MUST NOT 被视为确认

#### Scenario: Plugin and Skill content are organized by user scenario
- **WHEN** 维护 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容
- **THEN** Skill（技能）入口和 `references/`（参考文件）MUST 按用户场景组织，而不是按 YAML（配置格式）字段或 script（脚本）函数平铺
- **THEN** 用户场景 MUST 覆盖初次启用 PR Flow（拉取请求流程）、review gate（审查门禁）、hotfix（热修复）、cleanup（清理）、GitHub（代码托管平台）远端配置建议和最终写入确认
- **THEN** questionnaire（问答模板）MUST 作为固定执行模板服务这些场景，但场景组织要求不只限于 questionnaire（问答模板）
- **THEN** Plugin（插件）级验收范围 MUST include init（初始化）相关的 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 和 `skills/pr-flow/SKILL.md`（总入口）描述或路由内容
- **THEN** unrelated complete、cleanup、hotfix 和 tweak（收尾、清理、热修复、小改）Skill（技能）内容 MUST NOT be reorganized unless it directly describes init（初始化）

#### Scenario: Draft and validation rules are fixed references
- **WHEN** agent（代理）生成配置草案
- **THEN** agent（代理）MUST 读取 `references/config-draft.md`（配置草案规则）
- **WHEN** agent（代理）执行写入前校验或展示校验摘要
- **THEN** agent（代理）MUST 读取 `references/validation.md`（校验规则）
- **THEN** agent（代理）MUST 按这些固定参考文件展示草案、问题、影响和建议
