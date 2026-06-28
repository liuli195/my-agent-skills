# pr-flow-plugin Specification

## Purpose
Define the reusable PR Flow（拉取请求流程）Plugin（插件） for personal repositories, including repository configuration, diagnose stop states, complete lifecycle handling, cleanup, hotfix, tweak, and configurable review gate behavior.
## Requirements
### Requirement: PR Flow Plugin package
系统 MUST 提供 `pr-flow` Plugin（插件），用于个人仓库复用 PR Flow（拉取请求流程）。

#### Scenario: Codex plugin structure
- **WHEN** 发布 `pr-flow` Plugin
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单）MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Claude plugin structure
- **WHEN** 发布 `pr-flow` Plugin
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单）MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Skill entrypoints
- **WHEN** 安装 `pr-flow` Plugin
- **THEN** 插件包 MUST 提供 `pr-flow`、`pr-flow-init`、`pr-flow-complete`、`pr-flow-cleanup`、`pr-flow-hotfix` 和 `pr-flow-tweak` Skill（技能）
- **THEN** 这些 Skill MUST 调用共享确定性脚本，而不是复制多套流程逻辑

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

### Requirement: Diagnose stop states
系统 MUST 提供 diagnose（诊断）入口，用于解释当前 PR Flow 卡点，并输出固定 stop state（停机状态）。

#### Scenario: Missing remote head branch
- **WHEN** 当前分支没有对应远端 head branch（功能分支）
- **THEN** diagnose MUST 输出 `PUSH_REQUIRED`
- **THEN** diagnose MUST 提示用户先 push（推送）当前分支

#### Scenario: Required checks need external progress
- **WHEN** GitHub checks（检查）未完成或需要外部系统启动
- **THEN** diagnose MUST 输出 `DISPATCH_REQUIRED`
- **THEN** diagnose MUST 保留可继续执行的下一步提示

#### Scenario: Review or checks block merge
- **WHEN** review gate（审查门禁）或 required checks（必需检查）阻塞 PR
- **THEN** diagnose MUST 输出 `REPLY_OR_FIX_REQUIRED`

#### Scenario: Draft PR needs ready transition
- **WHEN** PR 是 draft（草稿）且 checks（检查）已通过
- **THEN** diagnose MUST 输出 `DISPATCH_REQUIRED`
- **THEN** diagnose MUST 使用 `pr_is_draft` 作为 reason（原因）
- **THEN** diagnose MUST 提供将 PR 转为 ready（可审查）的下一步提示

#### Scenario: No stop state remains
- **WHEN** 当前 PR 没有 push、checks、review、draft 或异常阻塞
- **THEN** diagnose MUST 输出 `ready`
- **THEN** diagnose MUST 以成功退出码返回
- **THEN** diagnose MUST 提供 `complete` 作为下一步提示

#### Scenario: Unexpected state
- **WHEN** 系统无法安全判断下一步
- **THEN** diagnose MUST 输出 `EXCEPTION_REQUIRED`
- **THEN** diagnose MUST 保留足够上下文供人工判断

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Complete happy path
- **WHEN** 当前分支可以创建或同步 PR
- **THEN** 系统 MUST 创建或同步 PR
- **THEN** 系统 MUST 等待配置中的 checks
- **THEN** 系统 MUST 执行配置中的 review gate
- **THEN** 系统 MUST 按配置中的 merge strategy（合并策略）合并 PR
- **THEN** 系统 MUST 执行 cleanup（清理）

#### Scenario: No dry run mode
- **WHEN** 用户运行 complete、cleanup、hotfix 或 tweak
- **THEN** 系统 MUST 执行真实流程
- **THEN** 系统 MUST NOT 提供 dry-run（试运行）分支逻辑

#### Scenario: Head locked merge
- **WHEN** 系统合并 PR
- **THEN** 系统 MUST 锁定当前 head commit（头提交）
- **THEN** 系统 MUST NOT 合并已经移动的 head branch

#### Scenario: Configured merge strategy
- **WHEN** 配置声明 `merge`、`squash` 或 `rebase`
- **THEN** 系统 MUST 严格按配置选择 GitHub merge strategy

### Requirement: Review gate modes
系统 MUST 支持 GitHub（代码托管平台）、local（本地）、dual（双门禁）和 skip（跳过）四种 review gate（审查门禁）模式。

#### Scenario: Local review evidence
- **WHEN** `reviewGate.mode` 为 `local` 或 `dual`
- **THEN** 系统 MUST 校验本地 review evidence（审查证据）
- **THEN** 首版 MUST 支持配置的 JSON review pass evidence（审查通过证据），默认路径为 `.pr-flow/review-pass.json`
- **THEN** 本地 evidence MUST 匹配当前 base、head 和 diff（差异）

### Requirement: Cross-agent-review evidence generation
系统 MUST 保持 `cross-agent-review`（跨代理审查）输出可被调用方读取，并由主 agent（主代理）在通过后生成 PR Flow local/dual review gate（本地/双门禁审查门禁）所需 evidence（证据）。

#### Scenario: Prepared input paths
- **WHEN** 系统运行 `cross-agent-review`
- **THEN** 输入快照 MUST 写入 `.local/cross-agent-review/<change>/<head>/prepared-inputs/`

#### Scenario: Strict reviewer output
- **WHEN** reviewer（审查代理）返回 findings（发现项）
- **THEN** 每个 finding MUST 使用 `CRITICAL`、`IMPORTANT`、`WARNING` 或 `SUGGESTION` severity（严重级别）
- **THEN** 主 agent（主代理）MUST 把缺失 severity 或使用别名的 finding 视为 invalid reviewer finding（无效审查发现）
- **THEN** 外部自定义 reviewer MUST 在使用本版本前迁移旧 severity aliases（严重级别别名）

### Requirement: Cleanup merged PR
系统 MUST 提供 cleanup（清理）入口，安全清理已合并 PR 的本地和远端分支。

#### Scenario: Cleanup merged PR
- **WHEN** PR 已合并且工作区干净
- **THEN** 系统 MUST 删除已合并 PR 的远端 head branch
- **THEN** 系统 MUST 切回并同步 base branch
- **THEN** 系统 MUST 删除本地 head branch
- **THEN** 系统 MUST 输出最终分支状态

#### Scenario: Cleanup refuses unsafe state
- **WHEN** PR 未合并、工作区不干净、head branch 等于 base branch 或 head branch 不匹配当前 PR
- **THEN** cleanup MUST 拒绝执行
- **THEN** cleanup MUST 输出 `EXCEPTION_REQUIRED` 或更具体的 stop state

#### Scenario: Cleanup branch protection scope
- **WHEN** cleanup 处理已合并 PR
- **THEN** 系统 MUST NOT 删除 base branch（目标分支）
- **THEN** 首版 MUST NOT 查询或自动配置 GitHub Branch Protection（GitHub 分支保护）或 Rulesets（规则集）

#### Scenario: Cleanup does not invent authorization
- **WHEN** cleanup 按配置和当前状态可安全执行
- **THEN** 系统 MUST NOT 因 authorization phrase（授权短语）功能额外要求确认

### Requirement: Hotfix direct push path
系统 MUST 提供 hotfix（热修复）路径，用于紧急直推显式允许的目标分支。

#### Scenario: Hotfix allowed branch
- **WHEN** 用户运行 hotfix
- **THEN** 目标分支 MUST 在配置中显式 `allowHotfixPush: true`
- **THEN** 用户 MUST 显式指定目标分支

#### Scenario: Hotfix base matches target
- **WHEN** 用户运行 hotfix
- **THEN** 系统 MUST fetch（拉取）目标远端分支
- **THEN** 当前提交 MUST 基于目标分支最新 head commit
- **THEN** 系统 MUST 拒绝旧 base（基线）或错误 base 的 hotfix

#### Scenario: Hotfix verification and confirmation
- **WHEN** 用户运行 hotfix
- **THEN** 系统 MUST 先确认 authorization phrase 配置存在且算法受支持
- **THEN** 系统 MUST 运行 `hotfix.verifyCommand`
- **THEN** `hotfix.verifyCommand` MAY 使用 build-and-verify（构建与验证）`--full`（完整）模式
- **THEN** 验证通过后系统 MUST 校验 authorization phrase
- **THEN** 确认通过后系统 MAY push 到受保护分支

#### Scenario: Hotfix remote verification
- **WHEN** hotfix push 完成
- **THEN** 系统 MUST 回读远端目标分支
- **THEN** 远端目标分支 MUST 等于预期 head commit
- **THEN** 系统 MUST 写入最小本地审计记录

### Requirement: PR Flow preserves build-and-verify verification mode boundaries
PR Flow（拉取请求流程）MUST preserve the boundary between default fast verify（快速验证） and explicit full verify（完整验证） when it references build-and-verify（构建与验证） commands.

#### Scenario: Complete path does not force full verification
- **WHEN** 用户运行 PR Flow complete（拉取请求流程收尾）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `build-and-verify verify --full` unless the full command is supplied by an external PR CI（拉取请求持续集成）check
- **THEN** local review gate（本地审查门禁）evidence MUST NOT be treated as a request to run full verify（完整验证）

#### Scenario: Hotfix direct push uses explicit full verification command
- **WHEN** 用户运行 PR Flow hotfix（拉取请求流程热修复）
- **THEN** PR Flow（拉取请求流程） MAY run the configured `hotfix.verifyCommand`
- **THEN** 本仓库 `hotfix.verifyCommand` MAY be `python plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify.py verify --project . --full`
- **THEN** 该 full verify（完整验证） usage（使用） MUST remain explicit in `.pr-flow/config.yaml`

#### Scenario: Tweak path does not force full verification
- **WHEN** 用户运行 PR Flow tweak（拉取请求流程小改）
- **THEN** PR Flow（拉取请求流程） MUST NOT invoke `build-and-verify verify --full`
- **THEN** tweak（小改） path（路径） MUST continue to skip review gate（审查门禁） without upgrading verification mode（验证模式）

#### Scenario: Unknown verification mode is not inferred
- **WHEN** PR Flow（拉取请求流程） consumes review gate（审查门禁） evidence or check status（检查状态）
- **THEN** PR Flow（拉取请求流程） MUST NOT infer that full verify（完整验证） has run unless the evidence or external check explicitly identifies the full command
- **THEN** PR Flow（拉取请求流程） MUST keep fast verify（快速验证） and full verify（完整验证） evidence distinct

### Requirement: Tweak PR path
系统 MUST 提供 tweak（非 bug 小改动）路径，用于跳过 review gate 但保留 PR 流程。

#### Scenario: Tweak requires PR
- **WHEN** 用户运行 tweak
- **THEN** 系统 MUST 创建或同步 PR
- **THEN** 系统 MUST 等待 checks、合并 PR 并执行 cleanup
- **THEN** 系统 MUST 跳过 review gate

#### Scenario: Tweak reason
- **WHEN** 用户运行 tweak
- **THEN** 用户 MUST 提供 reason（原因）
- **THEN** 系统 MUST 在 PR body（拉取请求正文）中标记 tweak 路径和 reason

### Requirement: Authorization phrase confirmation
系统 MUST 支持仓库共用 authorization phrase，用于替代用户说“我确认”。

#### Scenario: Authorization phrase storage
- **WHEN** 配置声明 authorization phrase
- **THEN** 配置 MUST 只保存 hash（哈希值）和算法
- **THEN** 首版算法 MUST 支持 MD5（摘要算法）
- **THEN** 系统 MUST NOT 保存明文短语

#### Scenario: Authorization phrase scope
- **WHEN** 一个流程步骤本来需要用户显式确认
- **THEN** 系统 MUST 使用 authorization phrase 确认
- **THEN** 确认只在当前命令内有效
- **THEN** authorization phrase MUST NOT 改变原流程是否需要确认

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
- **THEN** validate（校验）MUST 输出 error（错误）、warning（警告）或 remote task（远端待办）
- **THEN** error（错误）MUST 表示配置本身不可用
- **THEN** warning（警告）MUST 表示配置可写入但存在流程风险
- **THEN** remote task（远端待办）MUST 表示需要用户或 agent（代理）另行处理的 GitHub（代码托管平台）配置

#### Scenario: Validation errors block init writes
- **WHEN** init（初始化）准备写入已确认配置
- **AND** validate（校验）对该配置输出一个或多个 error（错误）
- **THEN** init（初始化）MUST stop without writing `.pr-flow/config.yaml`、PR body template（拉取请求正文模板）或 `.pr-flow/.gitignore`
- **THEN** warning（警告）和 remote task（远端待办）MAY be shown before final confirmation, but MUST NOT block writing by themselves

#### Scenario: Validate checks hotfix dependencies
- **WHEN** 任一 `branches.<branch>.allowHotfixPush` 为 `true`
- **THEN** validate（校验）MUST 要求存在 `authorization.phraseHashAlgorithm: md5`
- **THEN** validate（校验）MUST 要求存在非空 `authorization.phraseHash`
- **THEN** validate（校验）MUST 要求存在非空 `hotfix.verifyCommand`
- **THEN** validate（校验）MUST 要求该分支存在非空 `remote`
- **THEN** validate（校验）MUST 输出 Rulesets bypass（规则集绕过权限）远端待办

#### Scenario: Validate checks review gate dependencies
- **WHEN** `reviewGate.mode` 是 `github` 或 `dual`
- **THEN** validate（校验）MUST 输出 required review（必需审查）远端待办
- **WHEN** `reviewGate.mode` 是 `local` 或 `dual`
- **THEN** validate（校验）MUST 要求存在非空 `reviewGate.evidencePath`
- **THEN** validate（校验）MUST 输出 review-pass.json（审查通过文件）字段契约 warning（警告）

#### Scenario: Validate checks GitHub setup dependencies
- **WHEN** 配置声明 required checks（必需检查）意图
- **THEN** validate（校验）MUST 输出 GitHub Rulesets（GitHub 规则集）远端待办
- **WHEN** 配置声明 merge strategy（合并方式）
- **THEN** validate（校验）MUST 输出对应 merge method（合并方式）需要在 GitHub（代码托管平台）启用的远端待办
- **WHEN** 配置启用 auto-delete head branch（自动删除源分支）意图
- **THEN** validate（校验）MUST 输出 cleanup（清理）职责重叠 warning（警告）

#### Scenario: Validate preserves verification mode boundaries
- **WHEN** validate（校验）读取 review gate evidence（审查门禁证据）路径或 setup.github（GitHub 配置建议）
- **THEN** validate（校验）MUST NOT 推断 full verify（完整验证）已经运行
- **THEN** validate（校验）MUST 保持 full verify（完整验证）仅作为 hotfix.verifyCommand（热修复验证命令）或 PR CI（拉取请求持续集成）建议的显式配置

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire is fixed
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** agent（代理）MUST 先读取 `references/questionnaire.md`（问答模板）
- **THEN** questionnaire（问答模板）MUST 定义固定问题、固定选项、选择后果和跳转规则
- **THEN** agent（代理）MUST NOT 临场编造初始化问题或跳过最终写入确认
- **THEN** 用户沉默 MUST NOT 被视为确认
- **THEN** 最终写入确认 MUST 提供 3 个固定选项：不写入放弃本次配置、只写入本地配置、按 remote tasks（远端待办）完成 GitHub（代码托管平台）配置后再写入本地配置
- **THEN** questionnaire（问答模板）MUST 明确 GitHub（代码托管平台）配置由 agent（代理）执行
- **THEN** questionnaire（问答模板）MUST 明确插件不提供 GitHub（代码托管平台）配置脚本能力

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: Remote guidance shows current state before recommendations
- **WHEN** agent（代理）prepares the confirmation summary for `pr-flow-init`
- **THEN** it MUST show the current GitHub（代码托管平台）state for Rulesets（规则集）, branch protection（分支保护）, merge methods（合并方式）, auto-delete head branch（自动删除源分支）, and PR status checks（拉取请求状态检查） when that state has been inspected
- **THEN** it MUST show recommended GitHub setup separately from local files that will be written
- **THEN** it MUST NOT imply that GitHub setup has been applied

#### Scenario: Remote tasks use GitHub official rule names
- **WHEN** GitHub setup guidance includes branch protection（分支保护）
- **THEN** it MUST describe the task as creating or updating a branch ruleset（分支规则集） for the selected target branches
- **THEN** it MUST name `Require a pull request before merging`（合并前要求拉取请求） as the rule that requires protected branches to change through PR（拉取请求）
- **THEN** it MUST set `required_approving_review_count: 0` unless the user explicitly chooses an approving review（批准审查） requirement

#### Scenario: PR status checks are concrete or explicit future work
- **WHEN** the user chooses to require PR status checks（拉取请求状态检查）
- **AND** no concrete PR check names are available from inspected workflows
- **THEN** the GitHub setup guidance MUST record a task to add or identify PR status checks before enabling `Require status checks to pass before merging`（合并前要求状态检查通过）
- **THEN** it MUST NOT invent check names

#### Scenario: CodeQL security check is an explicit ruleset task
- **WHEN** the user chooses to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST record a Rulesets（规则集）task to configure `Require code scanning results`（要求代码扫描结果）
- **THEN** it MUST select `CodeQL` as the code scanning tool（代码扫描工具）
- **THEN** it MUST use GitHub 默认阈值 for code scanning thresholds（代码扫描阈值）
- **WHEN** the user chooses not to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST NOT include a CodeQL（代码扫描工具）remote task（远端待办）

#### Scenario: Confirmation summary is user-readable first
- **WHEN** agent（代理）shows the init draft before final confirmation
- **THEN** it MUST first show user-readable tables for local writes, GitHub current state, GitHub recommendations, and validation results
- **THEN** it MUST NOT show a complete YAML（配置格式）draft
- **THEN** it MAY show only necessary field paths or small field fragments after the user-readable summary

