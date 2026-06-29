# pr-flow-plugin Specification

## Purpose
Define the reusable PR Flow（拉取请求流程）Plugin（插件） for personal repositories, including repository configuration, diagnose stop states, complete lifecycle handling, cleanup, hotfix, tweak, and configurable review gate behavior.
## Requirements
### Requirement: PR Flow Plugin package
系统 MUST 提供 `pr-flow` Plugin（插件），用于个人仓库复用 PR Flow（拉取请求流程）。

#### Scenario: Skill entrypoints expose source repository commands
- **WHEN** maintainer（维护者）reads a PR Flow Skill（拉取请求流程技能）inside the source repository（源码仓库）
- **THEN** command examples for diagnose、complete、cleanup、hotfix and tweak（诊断、收尾、清理、热修复和小改） MUST point to `plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- **THEN** command examples MUST NOT point to a missing root-level `scripts/pr_flow.py`
- **THEN** command examples MUST NOT point to an installed-skill relative `../pr-flow/scripts/pr_flow.py` path when documenting source repository（源码仓库） usage（用法）

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

#### Scenario: Feature branch has no PR yet
- **WHEN** diagnose（诊断）runs on a non-base branch（非目标分支）
- **AND** the branch already has upstream（上游分支）
- **AND** `gh pr view`（查看拉取请求） reports no PR（拉取请求）
- **THEN** diagnose（诊断） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** diagnose（诊断） MUST use `pr_missing` as reason（原因）
- **THEN** diagnose（诊断） MUST provide `complete`（收尾） as the next command（下一步命令）

### Requirement: Complete PR lifecycle
系统 MUST 提供 complete（完整流程），从当前分支创建或同步 PR 到合并后清理。

#### Scenario: Safe auto-push before PR lifecycle
- **WHEN** 用户在功能分支运行 complete（收尾）
- **AND** 本地工作区干净
- **AND** 当前分支不是 `defaults.baseBranch`（默认目标分支）
- **AND** GitHub（代码托管平台）远端确认当前分支没有 active rules（有效规则）
- **AND** 当前分支没有 upstream（上游分支）或本地提交尚未推送
- **THEN** complete（收尾） MUST 执行普通 `git push`（推送）
- **THEN** 无 upstream（上游分支）时 MUST 使用 `git push -u <remote> <branch>`
- **THEN** 已有 upstream（上游分支）时 MUST 使用 `git push`
- **THEN** 推送成功后 MUST 继续创建或同步 PR（拉取请求）

#### Scenario: Auto-push refuses unsafe branch
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 当前分支等于 `defaults.baseBranch`（默认目标分支）或 GitHub（代码托管平台）远端显示当前分支有 active rules（有效规则）
- **THEN** complete（收尾） MUST NOT push（推送）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理）

#### Scenario: Auto-push fails closed on uncertainty
- **WHEN** complete（收尾）准备自动推送当前分支
- **AND** 本地工作区不干净、GitHub（代码托管平台）保护状态查询失败、保护状态无法解析或 `git push`（推送）失败
- **THEN** complete（收尾） MUST NOT continue to create, sync, or merge PR（拉取请求）
- **THEN** complete（收尾） MUST output `EXCEPTION_REQUIRED`（需要人工处理） for dirty or uncertain state
- **THEN** complete（收尾） MUST output `PUSH_REQUIRED`（需要推送） when `git push`（推送） itself fails

#### Scenario: Rulesets block merge
- **WHEN** `gh pr merge`（合并拉取请求） fails because the base branch policy（目标分支策略） prohibits the merge（合并）
- **THEN** complete（收尾） MUST output `DISPATCH_REQUIRED`（需要外部进展）
- **THEN** complete（收尾） MUST use `ruleset_merge_blocking` as reason（原因）
- **THEN** complete（收尾） MUST preserve the original GitHub（代码托管平台） error text for diagnosis（诊断）

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

#### Scenario: Validate reports CodeQL default setup task
- **WHEN** validate（校验） reads a config（配置） that declares CodeQL code scanning（代码扫描） guidance
- **THEN** validate（校验） MUST output a remote task（远端待办） to enable CodeQL Default setup（CodeQL 默认配置）
- **THEN** validate（校验） MUST output a remote task（远端待办） to configure GitHub Rulesets（GitHub 规则集） CodeQL code scanning（CodeQL 代码扫描）
- **THEN** validate（校验） MUST NOT call GitHub API（GitHub 接口） or `gh` CLI（GitHub 命令行工具） to inspect remote CodeQL Default setup（CodeQL 默认配置）
- **THEN** validate（校验） MUST NOT report remote CodeQL Default setup（CodeQL 默认配置） as confirmed
- **WHEN** the project（项目） has a local workflow（工作流） using `codeql-action`
- **THEN** validate（校验） MUST still output the CodeQL Default setup（CodeQL 默认配置） remote task（远端待办）

### Requirement: PR Flow init uses scenario-oriented progressive-disclosure guidance
系统 MUST 让 PR Flow init（拉取请求流程初始化）的 Plugin（插件）和 Skill（技能）内容使用用户场景组织和 progressive disclosure（渐进式披露），并用固定问答模板约束 agent（代理）初始化流程。

#### Scenario: Questionnaire separates CodeQL security from status checks
- **WHEN** agent（代理）执行 `pr-flow-init` Skill（初始化技能）
- **THEN** questionnaire（问答模板）MUST ask CodeQL security check（CodeQL 安全检查） before PR status checks（拉取请求状态检查）
- **THEN** if the user does not enable CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST NOT offer `Analyze Python`, `Analyze (python)`, `Analyze (actions)` or `CodeQL` CodeQL-related checks（CodeQL 相关检查）
- **THEN** if the user enables CodeQL security check（CodeQL 安全检查）, the later PR status checks（拉取请求状态检查） question MUST default to non-security-scan checks（非安全扫描检查） and MUST NOT present CodeQL-related checks（CodeQL 相关检查） as status check（状态检查） options
- **THEN** questionnaire（问答模板）MUST treat `Require code scanning results`（要求代码扫描结果） as the primary CodeQL security gate（CodeQL 安全门禁）

### Requirement: PR Flow init presents executable GitHub setup guidance
PR Flow init（拉取请求流程初始化）MUST separate local config writes（本地配置写入） from GitHub setup guidance（GitHub 配置建议） and present GitHub guidance as executable manual tasks.

#### Scenario: CodeQL security check uses default setup by default
- **WHEN** the user chooses to enable CodeQL security check（CodeQL 安全检查）
- **THEN** GitHub setup guidance MUST record a Rulesets（规则集）task to configure `Require code scanning results`（要求代码扫描结果）
- **THEN** GitHub setup guidance MUST record a task to enable CodeQL Default setup（CodeQL 默认配置）
- **THEN** it MUST select `CodeQL` as the code scanning tool（代码扫描工具）
- **THEN** it MUST use GitHub 默认阈值 for code scanning thresholds（代码扫描阈值）
- **THEN** local config draft（本地配置草案） MUST keep using `setup.github.codeScanning`（代码扫描配置） without adding `defaultSetup` or equivalent new fields（等价新字段）

