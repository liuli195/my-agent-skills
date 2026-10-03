# test-framework-plugin Specification

## Purpose

This capability keeps the MySpec（自有规格） id `test-framework-plugin` to model the rename（改名） of an existing capability. Its shipped Plugin（插件） and Skill（技能） name is `build-and-verify`, which is the repository build（构建检查） and verify（验证） entry point.

## Requirements

### Requirement: Guided initialization protects existing configuration
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 在覆盖已有配置前保护用户已有 `.build-and-verify/config.json`（配置文件）。

#### Scenario: Existing config requires explicit overwrite confirmation
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 展示覆盖摘要
- **THEN** agent（代理） MUST 等待用户明确确认覆盖
- **THEN** agent（代理） MUST NOT 因用户沉默而覆盖已有配置

#### Scenario: Existing config is backed up before overwrite
- **WHEN** 用户确认覆盖已有 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 在 backups（备份）目录不存在时先创建该目录
- **THEN** agent（代理） MUST 先复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）
- **THEN** agent（代理） MUST 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`
- **THEN** agent（代理） MUST NOT 要求用户单独选择备份路径
- **THEN** agent（代理） MUST 在写入结果中报告备份路径
### Requirement: Guided initialization validates config and environment before completion
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 在最终写入确认前执行定向依赖检查和环境检查，并在写入后执行配置校验。

#### Scenario: Config structure is validated after write
- **WHEN** agent（代理）写入 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/cache/`、`/runs/` 和 `/backups/`
- **THEN** agent（代理） MUST 校验配置结构符合 build-and-verify（构建与验证）runner（运行器）契约
- **THEN** agent（代理） MUST 报告配置校验结果

#### Scenario: Targeted dependency checks report issues before write without blocking write
- **WHEN** 配置草案包含可识别依赖特征
- **THEN** agent（代理） MUST 在最终写入确认前执行 targeted dependency checks（定向依赖检查）
- **THEN** 配置包含 `pytestXdistWorkers`（Pytest 工作进程数）时，agent（代理） MUST 检查 `pytest-xdist`（Pytest 并行插件）是否可用
- **THEN** 命令调用外部可执行文件时，agent（代理） MUST 检查该入口是否可找到
- **THEN** `paths`（受影响路径）或 `inputs`（缓存输入）指向不存在文件或目录时，agent（代理） MUST 提示用户确认
- **THEN** agent（代理） MUST 允许用户在存在依赖或环境问题时仍写入配置
- **THEN** agent（代理） MUST 明确列出问题、影响和建议
- **THEN** agent（代理） MUST NOT 未经用户授权就安装依赖或修改外部环境

#### Scenario: Environment checks report issues before write without blocking write
- **WHEN** agent（代理）准备写入 `.build-and-verify/config.json`（配置文件）
- **THEN** agent（代理） MUST 在最终写入确认前执行 environment checks（环境检查）
- **THEN** agent（代理） MUST 检查目标仓库路径存在且是目录
- **THEN** agent（代理） MUST 检查配置目录可创建或可写入
- **THEN** 覆盖已有配置时，agent（代理） MUST 检查备份目录可创建且备份路径仍在目标仓库内
- **THEN** agent（代理） MUST 允许用户在存在依赖或环境问题时仍写入配置
- **THEN** agent（代理） MUST 明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题
### Requirement: Full verify provides non-blocking total performance warnings
Build and Verify（构建与验证） MUST 接受可选正整数 `verify.fullBudgetSeconds`（完整验证预算秒数）。明确本机执行时该值同时约束一次快速或完整验证；强制开关关闭，或云端、拉取请求及可靠持续集成场景时，预算告警 MUST NOT 替代真实功能结果。

#### Scenario: Full verify finishes before budget
- **WHEN** 完整验证在配置预算内完成全部检查
- **THEN** 系统 MUST NOT 输出 `performance-warning`（性能警告）
- **THEN** 退出状态 MUST 由真实检查结果确定

#### Scenario: Full verify exceeds budget
- **WHEN** 本机强制开关关闭，或执行地点为云端、拉取请求或可靠持续集成
- **AND** 完整验证超过配置预算
- **THEN** 系统 MUST 完成配置检查后输出总耗时、预算和超出时长告警
- **THEN** 告警 MUST NOT 改变功能检查确定的退出状态
- **THEN** 云端、拉取请求及可靠持续集成 MUST 保留既有完整验证预算告警行为

#### Scenario: Functional failure remains authoritative
- **WHEN** 任一检查失败、异常或发生单项超时
- **THEN** 系统 MUST 返回真实失败
- **THEN** 开关关闭、预算内完成或仅有预算告警 MUST NOT 将真实失败变为通过

#### Scenario: Invalid full budget is rejected
- **WHEN** 配置预算不是正整数，或 `verify.enforceLocalBudget`（本机预算强制开关）不是布尔值
- **THEN** 系统 MUST 在启动检查前明确拒绝并报告无效字段
### Requirement: Full verify records a fixed performance report on demand or over budget
Build and Verify（构建与验证） MUST 保留固定报告路径和既有核心计时字段，并兼容补充本机截止与诊断状态；报告 MUST NOT 依赖业务测试输出结构。

#### Scenario: Explicit report is written within budget
- **WHEN** 用户运行 `verify --full --performance-report`（完整验证性能报告）
- **THEN** 系统 MUST 写入 `.build-and-verify/runs/performance-report.json`（性能报告）
- **THEN** 报告 MUST 与真实退出结果一致

#### Scenario: Over-budget run writes report automatically
- **WHEN** 本机快速或完整验证超预算、发生总截止，或进入诊断模式
- **THEN** 系统 MUST 自动记录报告并输出报告路径
- **THEN** 总截止报告 MUST 包含失败原因、耗时、预算、未完成及未启动检查
- **THEN** 未完成检查 MUST NOT 被报告为已通过

#### Scenario: Unrequested under-budget run does not touch the fixed report
- **WHEN** 非诊断验证未超预算且未请求性能报告
- **THEN** 系统 MUST NOT 创建、覆盖或删除已有固定报告

#### Scenario: Report schema is stable
- **WHEN** 系统写入性能报告
- **THEN** 报告 MUST 保留 `schemaVersion`（结构版本）、`runtimeVersion`（运行时版本）、`generatedAt`（生成时间）、`totalSeconds`（总秒数）、`budgetSeconds`（预算秒数）、`overBudget`（超预算状态）、`verificationStatus`（验证状态）和 `checks`（检查列表）核心字段
- **THEN** 本机及诊断报告 MUST 兼容补充执行地点、诊断标记、原因、未完成及未启动信息
- **THEN** 生成时间 MUST 使用协调世界时；无预算时预算及超预算字段 MUST 为 null（空值）
- **THEN** 检查列表 MUST 按配置顺序记录检查编号、状态及耗时

#### Scenario: Report failure does not block verification
- **WHEN** 报告无法写入
- **THEN** 系统 MUST 输出 `performance-report-warning`（性能报告警告）
- **THEN** 报告错误 MUST NOT 将真实失败改为通过或取消本机总截止

#### Scenario: Incomplete full verification does not produce performance output
- **WHEN** 豁免场景的既有完整验证未返回全部已选检查结果
- **THEN** 系统 MUST 保留既有不计算完整预算及不覆盖固定报告的行为
- **THEN** 本机总截止 MUST 仍记录未完成及未启动状态并返回失败

#### Scenario: Fast verification does not touch performance reporting
- **WHEN** 非本机且非诊断的快速验证运行
- **THEN** 系统 MUST 保留既有不评估完整预算、不改固定报告的行为
- **THEN** 本机快速验证 MUST 使用相同总预算，超预算时 MUST 记录报告

#### Scenario: Performance report requires full mode
- **WHEN** 用户显式提供 `--performance-report`（性能报告参数）但未提供 `--full`（完整模式参数）
- **THEN** 参数校验 MUST 在检查前失败并说明完整模式要求
- **THEN** 此约束 MUST NOT 阻止本机截止或诊断自动记录报告
### Requirement: Guided initialization supports optional full verification budget
Build and Verify Init（构建与验证初始化） MUST 允许用户选择可选正整数预算，不替任何项目写死数值，且 MUST 准确说明本机强制开关缺省开启。

#### Scenario: User enables full verification budget
- **WHEN** 用户选择配置验证预算
- **THEN** 问答及最终确认 MUST 展示用户确认数值，并说明该值用于本机单次快速与完整验证
- **THEN** 问答 MUST 说明本机缺省到时终止并失败，关闭开关仅告警，豁免场景保留既有行为
- **THEN** 生成配置 MUST 包含用户确认的预算数值，写后校验 MUST 检查预算与开关类型

#### Scenario: User leaves full verification budget disabled
- **WHEN** 用户不选择配置预算
- **THEN** 生成配置 MUST 省略预算字段
- **THEN** 插件模板 MUST NOT 强加项目专属性能目标
### Requirement: Build and Verify tests minimize repeated real entrypoints
Build and Verify（构建与验证） tests MUST keep real entrypoint coverage small and move repeated branch coverage to in-process（进程内） tests. Its 30-second target applies to the plugin's own test suite and is distinct from the repository-wide end-to-end full verification target.

#### Scenario: Init keeps a real E2E entrypoint
- **WHEN** repository tests cover build-and-verify init（构建与验证初始化）
- **THEN** at least one E2E（端到端测试） test MUST execute the real init（初始化） entrypoint
- **THEN** additional init（初始化） branch behavior MUST be tested in-process（进程内） unless it specifically verifies packaged entrypoint behavior
- **THEN** any additional real init（初始化） E2E（端到端测试） MUST be explicitly allowlisted as distinct packaged entrypoint behavior

#### Scenario: Verify keeps a real E2E entrypoint
- **WHEN** repository tests cover build-and-verify verify（构建与验证）
- **THEN** at least one E2E（端到端测试） test MUST execute the real default fast-verify（默认快速验证） entrypoint
- **THEN** additional verify（验证） branch behavior MUST be tested in-process（进程内） with a fake runner（假执行器）
- **THEN** any additional real verify（验证） E2E（端到端测试） MUST be explicitly allowlisted as distinct packaged entrypoint behavior

#### Scenario: Branch logic uses fake runner
- **WHEN** a test covers command planning, cache（缓存） selection, runtime（运行时） reporting, or failure classification
- **THEN** the test MUST call existing Python（Python 语言） functions in-process（进程内）
- **THEN** the test MUST use a fake runner（假执行器） instead of launching another real process

#### Scenario: Plugin test suite finishes within target
- **WHEN** the Build and Verify（构建与验证）plugin's own test suite is run for this change
- **THEN** `maxParallel`（最大并行检查数） MUST be fixed to `0`
- **THEN** Pytest（测试工具） workers（工作进程） MUST use `auto`
- **THEN** the measured plugin test-suite wall time MUST be less than or equal to 30 seconds
- **THEN** this plugin test-suite target MUST NOT redefine the repository-wide end-to-end full verification target
### Requirement: Build and Verify expands explicit glob cache inputs

Build and Verify（构建与验证） MUST expand explicit glob inputs（通配符缓存输入） into a stable project-local Git-visible file set so cached verification reflects the matched files.

#### Scenario: Matching files invalidate cached verification

- **WHEN** a matching file is added, removed, or its content changes
- **THEN** fast verify（快速验证） MUST NOT reuse the earlier passed-result cache（通过结果缓存）

#### Scenario: Glob inputs use the Git-visible file boundary

- **WHEN** an explicit glob input matches tracked files, visible untracked files, and ignored untracked files
- **THEN** the matched set MUST include the tracked and visible untracked files
- **THEN** the matched set MUST exclude ignored untracked files
- **THEN** an explicitly named literal file MUST retain its existing behavior even when ignored

#### Scenario: Future input is valid

- **WHEN** an explicit glob input currently matches no files
- **THEN** initialization and configuration review MUST report it as a valid Future Input（未来输入）
- **THEN** verification runtime MUST accept the empty matched set without repeated warnings
- **THEN** the first future matching file MUST invalidate the empty-set cache

#### Scenario: Glob input remains inside the project

- **WHEN** a glob input uses either path separator or matches candidate files
- **THEN** slash and backslash forms MUST produce the same matched set
- **THEN** absolute paths, parent traversal, and matching files outside the project MUST be rejected
- **THEN** non-matching files outside the project MUST NOT block verification

#### Scenario: Literal missing paths remain distinguishable

- **WHEN** initialization or configuration review encounters a missing literal path
- **THEN** it MUST distinguish that path from a Future Input（未来输入）
- **THEN** it MUST report that the literal path may contain a spelling error
### Requirement: Fast verification selects all checks for configuration changes

Build and Verify（构建与验证） MUST select every verification check executable in the current run scene when its repository configuration changes, while continuing to use cache entries created from that same current configuration. The default local scene includes all configured checks; the explicit PR（拉取请求）scene excludes checks with `pr: false`.

#### Scenario: Configuration is the only changed file

- **WHEN** the Build and Verify（构建与验证） configuration is the only changed file
- **THEN** fast verify（快速验证） MUST select every verification check executable in the current run scene
- **THEN** output MUST report the overall configuration-change selection reason once

#### Scenario: Current configuration cache remains reusable

- **WHEN** all checks selected by a configuration change already have passed-result cache（通过结果缓存） entries from the same current configuration and runtime version
- **THEN** fast verify（快速验证） MUST reuse those entries
- **THEN** cache entries from an earlier configuration MUST NOT be reused

#### Scenario: Invalid configuration stops scheduling

- **WHEN** the changed configuration is structurally invalid
- **THEN** verification MUST fail before scheduling any configured check

#### Scenario: Ordinary source changes retain path selection

- **WHEN** the configuration is unchanged and ordinary source files change
- **THEN** fast verify（快速验证） MUST continue selecting executable checks through their configured paths（受影响路径）
### Requirement: Guided initialization drafts generic repository checks
`build-and-verify-init` Skill（构建与验证初始化技能） MUST 为通用仓库生成可审查的 build（构建检查）和 verify（验证）配置草案。

#### Scenario: Node repository detection
- **WHEN** 目标仓库包含 `package.json`（包配置）
- **THEN** agent（代理） MUST 读取 `scripts`（脚本）并识别 build、test、lint 和 typecheck 等候选命令
- **THEN** agent（代理） MUST 展示候选 Node（节点运行时）checks（检查项）并等待用户选择
- **THEN** `check`（检查脚本）和 `verify`（验证脚本）候选 MUST 使用不同 check id（检查项标识）

#### Scenario: Python repository detection
- **WHEN** 目标仓库包含 Python（Python 语言）配置迹象
- **THEN** agent（代理） MUST 检查 `pyproject.toml`（项目配置）、`pytest.ini`（测试配置）、`tox.ini`（测试环境配置）、`noxfile.py`（任务配置）和 `requirements*.txt`（依赖清单）中的相关文件
- **THEN** agent（代理） MUST 优先建议 pytest（Python 测试运行器）和现有脚本作为候选 checks（检查项）
- **THEN** agent（代理） MUST 展示候选 Python（Python 语言）checks（检查项）并等待用户选择

#### Scenario: Generic candidate discovery
- **WHEN** 目标仓库包含 `Makefile`（任务文件）、`scripts/`（脚本目录）、`tests/`（测试目录）或 `myspec/`（开放规格目录）等通用信号
- **THEN** agent（代理） MUST 分类候选 checks（检查项），并展示 source（来源）、confidence（置信度）、reason（纳入理由）和 risk（风险提示）
- **THEN** agent（代理） MUST 先使用静态证据，不得在未确认时运行候选 command（命令）
- **THEN** 静态证据不足且探测能消除配置不确定性、成本可接受时，agent（代理） MAY 建议并在用户确认后运行完整命令组
- **THEN** 风险候选 MUST NOT 默认纳入配置草案

#### Scenario: Mixed repository
- **WHEN** 目标仓库同时包含 Node（节点运行时）、Python（Python 语言）或通用候选信号
- **THEN** agent（代理） MUST 同时展示多类候选 checks（检查项）
- **THEN** agent（代理） MUST 让用户选择纳入哪些 checks（检查项）

#### Scenario: No recognized ecosystem fallback
- **WHEN** 目标仓库没有可识别的已有配置、Node（节点运行时）、Python（Python 语言）或通用候选信号
- **THEN** agent（代理） MUST 继续使用固定 questionnaire（问答模板）
- **THEN** agent（代理） MUST 让用户手动提供 build（构建检查）和 verify（验证）候选命令
- **THEN** agent（代理） MUST 继续确认 `paths`（受影响路径）和运行参数，自动推导 `inputs`（缓存输入），并使用默认备份路径完成覆盖备份和配置校验

#### Scenario: Draft config includes paths and inputs
- **WHEN** agent（代理）生成配置草案
- **THEN** 草案 MUST 同时支持 `build.checks`（构建检查项）和 `verify.checks`（验证检查项）
- **THEN** check id（检查项标识） MUST 使用短横线格式，例如 `build.node` 或 `verify.python-tests`
- **THEN** command（命令）默认 MUST 使用字符串形式
- **THEN** agent（代理） MUST 只在用户明确要求更稳定参数边界时使用列表形式 command（命令）
- **THEN** agent（代理） MUST 为 verify checks（验证检查项）建议 `paths`（受影响路径）
- **THEN** agent（代理） MUST 从 `paths`（受影响路径）和 command（命令）来源推导 `inputs`（缓存输入）
- **THEN** agent（代理） MUST 在写入前等待用户确认 `paths`（受影响路径），并在最终写入摘要中展示自动推导的 `inputs`（缓存输入）

#### Scenario: Draft config explains runtime tuning
- **WHEN** 配置草案包含 `verify.maxParallel`（最大并行检查数）、`verify.timeoutSeconds`（超时秒数）、`checkParallel`（检查项间并行）或 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** agent（代理） MUST 逐项解释这些运行参数
- **THEN** agent（代理） MUST 等待用户确认后才能写入这些运行参数
- **THEN** agent（代理） MUST NOT 为没有 `auto`（自动）语义的工具硬编码 `auto`（自动）参数
### Requirement: Dynamic scanned verification inputs stay aligned
Build and Verify（构建与验证）配置指导 MUST 让动态扫描检查的快速选择和缓存输入覆盖其实际读取范围。

#### Scenario: Dynamic scan widens configuration scope
- **WHEN** 静态证据显示一个检查读取的范围大于其现有 `paths`（受影响路径）或 `inputs`（缓存输入）
- **THEN** 初始化和审查 MUST 建议以实际读取范围补全两者
- **THEN** 若该范围会让复合检查在不相关变更时运行，初始化和审查 MUST 建议拆分专用检查

#### Scenario: Confirmed candidate probe has a visible mutation
- **WHEN** 用户确认执行候选命令探测
- **THEN** agent（代理） MUST 在执行前展示完整命令组、总成本和可能副作用，并在执行前后核对 Git（版本管理）可见改动
- **THEN** 发现 Git（版本管理）可见改动时，agent（代理） MUST 停止后续建议和写入，保留现场，且 MUST NOT 自动清理或恢复
### Requirement: Build and Verify plugin package supports Claude and Codex
系统 MUST 提供轻量 `build-and-verify` Plugin（构建与验证插件），同一套能力 MUST 同时面向 Claude（Claude 版本）和 Codex（Codex 版本）。

#### Scenario: Codex plugin structure
- **WHEN** 发布 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.codex-plugin/plugin.json`
- **THEN** Codex manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Claude plugin structure
- **WHEN** 发布 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 包含 `.claude-plugin/plugin.json`
- **THEN** Claude manifest（清单） MUST 声明插件 `name`、`version`、`description` 和 `skills`

#### Scenario: Runtime and initialization skill surfaces
- **WHEN** 安装 `build-and-verify` Plugin（插件）
- **THEN** 插件包 MUST 提供 `build-and-verify` Skill（构建与验证技能）作为运行入口
- **THEN** 插件包 MUST 提供 `build-and-verify-init` Skill（构建与验证初始化技能）作为对话式初始化向导入口
- **THEN** `build-and-verify` Skill（技能） MUST 调用已安装的 `build-and-verify` CLI（命令行程序），而不是复制多套流程逻辑
- **THEN** `build-and-verify-init` Skill（技能） MUST 使用参考文件表达固定初始化流程，而不是新增命令行初始化脚本
### Requirement: Build and Verify initializes standard artifacts
系统 MUST 为目标仓库初始化最小构建检查和验证配置；已安装的 CLI（命令行程序）是唯一运行入口。

#### Scenario: Init creates standard files
- **WHEN** 用户对目标仓库运行 build-and-verify init（构建与验证初始化）
- **THEN** 系统 MUST 创建 `.build-and-verify/config.json`
- **THEN** 系统 MUST 创建 `.build-and-verify/.gitignore`
- **THEN** `.build-and-verify/.gitignore` MUST 包含 `/cache/`、`/runs/` 和 `/backups/`
- **THEN** 系统 MUST NOT 创建 `.build-and-verify/runtime/` 运行时快照

#### Scenario: Init writes confirmed config when provided
- **WHEN** 用户运行 `build-and-verify init --project <repo> --config <config-file> --overwrite`
- **THEN** 系统 MUST 使用 `<config-file>` 内容写入 `.build-and-verify/config.json`
- **THEN** 系统 MUST 在已有 `.build-and-verify/config.json` 时先备份到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`
- **THEN** 系统 MUST 在没有已有 `.build-and-verify/config.json` 时直接写入 confirmed config（已确认配置）
- **THEN** 系统 MUST 合并 `.build-and-verify/.gitignore` 默认规则而不是覆盖用户已有规则
- **THEN** 系统 MUST NOT 复制运行时快照到目标仓库

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.build-and-verify/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.build-and-verify/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files without overwrite
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json` 或 `.build-and-verify/.gitignore`
- **THEN** 系统 MUST 在没有 `--overwrite`（覆盖参数）时拒绝静默覆盖
- **THEN** 系统 MUST 返回 non-zero（非零）退出码并报告 target-repository-relative（目标仓库相对）冲突路径

#### Scenario: Init stays uncoupled from repository business logic
- **WHEN** 插件初始化目标仓库
- **THEN** 模板 MUST NOT 内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或任一具体仓库业务检查
- **THEN** 仓库业务检查 MUST 只通过 `.build-and-verify/config.json` 声明
### Requirement: Build and Verify provides unified configuration and commands
系统 MUST 通过一个配置文件和安装后的 CLI（命令行程序）表达 build（构建检查）与 verify（验证）行为。

#### Scenario: Config declares canonical checks
- **WHEN** 目标仓库配置 build-and-verify（构建与验证）
- **THEN** `.build-and-verify/config.json` MUST 支持 `build.checks`
- **THEN** `.build-and-verify/config.json` MUST 支持 `verify.checks`
- **THEN** `.build-and-verify/config.json` MUST NOT 要求独立的 `verify.fast.checks`
- **THEN** check（检查项）配置 MUST 使用 `checkParallel`（检查项间并行）表达 check（检查项）之间并行
- **THEN** check（检查项）配置 MUST 使用 `pytestXdistWorkers`（Pytest 工作进程数）表达 pytest（Python 测试框架）内部并行
- **THEN** check（检查项）配置 MUST NOT 支持旧 `parallel`（并行）字段

#### Scenario: Command entrypoint exposes minimum commands
- **WHEN** 目标仓库完成初始化
- **THEN** `build-and-verify build --project <repo>` MUST 运行 configured `build.checks`
- **THEN** `build-and-verify verify --project <repo>` MUST 运行默认 fast（快速验证）执行模式
- **THEN** `build-and-verify verify --project <repo> --full` MUST 运行完整 `verify.checks`
- **THEN** 命令 MUST NOT 在目标仓库复制、刷新或依赖 `.build-and-verify/runtime/`

#### Scenario: Full verify refreshes passed cache
- **WHEN** 用户运行 `build-and-verify verify --project <repo> --full`
- **THEN** 系统 MUST NOT 通过读取 cache（缓存）跳过 configured `verify.checks`
- **THEN** 成功通过的 check（检查项） MUST 使用同一套 cache key（缓存键）写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）结果 MUST NOT 写入 passed-result cache（通过结果缓存）

#### Scenario: Pytest xdist workers are explicit
- **WHEN** check（检查项）配置声明 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** `pytestXdistWorkers` MUST 是 `"auto"` 或正整数
- **THEN** 系统 MUST 仅对 pytest（Python 测试框架）命令应用 pytest-xdist（Pytest 并行插件）参数
- **THEN** 对字符串命令应用 pytest-xdist（Pytest 并行插件）参数时，系统 MUST 保留原命令的 shell（命令行解释器）语法、路径和引号
- **THEN** 系统 MUST 拒绝在非 pytest（Python 测试框架）命令上声明 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** 系统 MUST 在 pytest-xdist（Pytest 并行插件）不可用时报错，不得静默降级为串行
### Requirement: Build and Verify provides fast cache verification
系统 MUST 将 fast（快速验证）实现为 full（全量验证）标准检查项上的 changed-files（变更文件）筛选和 passed-result cache（通过结果缓存）。

#### Scenario: Fast verify selects configured checks by changed files
- **WHEN** 用户运行 `build-and-verify verify --project <repo>`
- **THEN** 系统 MUST 默认从 worktree（工作区）收集 changed files（变更文件）
- **THEN** 默认 worktree（工作区）来源 MUST 包含 staged tracked changes（已暂存已跟踪变更）、unstaged tracked changes（未暂存已跟踪变更）和 untracked non-ignored files（未跟踪且未忽略文件）
- **THEN** 系统 MUST 根据 configured check（配置检查项）的 `paths` 选择受影响 checks（检查项）

#### Scenario: Fast verify treats pathless checks as global checks
- **WHEN** configured verify check（配置验证检查项）没有 `paths`
- **THEN** 系统 MUST 将该 check（检查项）视为 global check（全局检查项）
- **THEN** 默认 fast verify（快速验证） MUST 在存在任意 changed file（变更文件）时选择该 check（检查项）
- **THEN** 默认 fast verify（快速验证） MUST 在没有 changed files（变更文件）时不选择该 check（检查项）
- **THEN** 没有 `inputs` 的 global check（全局检查项） MUST 使用当前 changed files（变更文件）作为 cache key（缓存键）的输入来源

#### Scenario: Cache uses passed results only
- **WHEN** 选中的 check（检查项）存在匹配 cache key（缓存键）
- **THEN** 系统 MUST 只复用 passed（已通过）的缓存结果
- **THEN** cache key（缓存键） MUST 覆盖 check id（检查项标识）、command（命令）、inputs（输入）、config（配置）、Python（运行器）版本、framework（框架）版本和 cache（缓存）版本
- **THEN** directory hashing（目录哈希） MUST 排除 `.build-and-verify/cache/`、`.git/` 和运行态缓存目录
- **THEN** 系统 MUST NOT 缓存 failed（失败）结果作为通过结果

#### Scenario: Cache miss runs selected check only
- **WHEN** 选中的 check（检查项）没有可用 passed-result cache（通过结果缓存）
- **THEN** 系统 MUST 运行该 check（检查项）自身
- **THEN** 系统 MUST NOT 因 cache miss（缓存未命中）自动运行 full（全量验证）
### Requirement: Build and Verify has no root-level Python test configuration dependency
系统 MUST 不依赖根目录 Python（Python 语言）测试配置来定义本仓库 build（构建检查）或 verify（验证）行为。

#### Scenario: Root pyproject test config is absent
- **WHEN** 本仓库 build-and-verify（构建与验证）配置完成迁移
- **THEN** 根目录 `pyproject.toml` MUST NOT 存在
- **THEN** `.build-and-verify/config.json` 中的 pytest（Python 测试运行器）命令 MUST 显式声明测试路径和所需命令参数

#### Scenario: Explicit pytest commands cover repository tests
- **WHEN** 仓库 `tests/`（测试目录）包含 `test_*.py`（Python 测试文件）
- **THEN** `.build-and-verify/config.json` 中 pytest（Python 测试运行器）命令声明的测试文件集合 MUST 与该目录中的文件集合一致

#### Scenario: No root wrapper entrypoint
- **WHEN** 本仓库活跃自动化和 guard（守卫）命令文件被检查
- **THEN** 它们 MUST NOT 引用根目录测试 wrapper（包装入口）
- **THEN** 它们 MUST 调用安装后的 `build-and-verify` CLI（命令行程序）
### Requirement: Build and Verify provides template-driven guided initialization
系统 MUST 通过 `build-and-verify-init` Skill（构建与验证初始化技能）提供模板化对话式初始化向导，用于为通用仓库生成 `.build-and-verify/config.json`（配置文件）。

#### Scenario: Guided initialization uses fixed questionnaire
- **WHEN** agent（代理）使用 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 指示 agent（代理）读取固定 questionnaire（问答模板）
- **THEN** questionnaire（问答模板） MUST 定义固定问题、固定选项、后果说明和跳转规则
- **THEN** questionnaire（问答模板） MUST 覆盖目标仓库路径确认、扫描授权、候选 check（检查项）确认、`paths`（受影响路径）确认、并行与超时确认、覆盖与最终写入确认
- **THEN** agent（代理） MUST 默认从 `paths`（受影响路径）和 command（命令）来源推导 `inputs`（缓存输入），并在最终写入确认摘要中展示
- **THEN** 覆盖已有配置时，agent（代理） MUST 使用默认备份路径，不得单独要求用户选择备份路径
- **THEN** agent（代理） MUST NOT 自由编造初始化问题或跳过最终写入确认

#### Scenario: Guided initialization uses progressive disclosure references
- **WHEN** 发布 `build-and-verify-init` Skill（构建与验证初始化技能）
- **THEN** Skill（技能） MUST 将固定问答模板放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将已有配置、Node（节点运行时）、Python（Python 语言）和通用候选识别规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将配置草案规则放在独立 reference（参考文件）
- **THEN** Skill（技能） MUST 将依赖检查、环境检查和配置校验规则放在独立 reference（参考文件）

#### Scenario: Guided initialization keeps command-line init non-interactive
- **WHEN** 用户运行 `build-and-verify init --project <repo>`
- **THEN** 系统 MUST 创建空的 `.build-and-verify/config.json`（配置文件）模板
- **THEN** 系统 MUST NOT 复制运行时快照到目标仓库
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中执行对话式问答
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中自动生成仓库业务检查项
### Requirement: Build and Verify uses the installed CLI without repository runtime snapshots
Build and Verify（构建与验证） build（构建） and verify（验证） commands MUST execute through the installed CLI（命令行程序） without copying a repository runtime（运行时） snapshot.

#### Scenario: Build and verify do not create a runtime snapshot
- **WHEN** 用户运行 `build-and-verify build`（构建）或 `build-and-verify verify`（验证）
- **THEN** commands MUST NOT create, refresh or require `.build-and-verify/runtime/`
### Requirement: Build and Verify 生命周期遵守统一 Codex 目录和旧来源迁移契约

Build and Verify MUST 让选择 Codex 的 `doctor --codex`、`doctor --all`、`init --codex`、`init --all` 和 `update` 复用共享生命周期规则：显式 `--codex-home` 优先，Orca 临时目录回退到用户默认目录，Codex 子进程和配置读写使用同一目录；`update` 发现 Claude/Codex（编码助手/代码代理）的旧插件记录时 MUST 在任何软件包、待处理状态或客户端写入前以非零结果停止并报告精确的 `init` 命令。完成迁移后重新运行 `update` MUST 刷新稳定来源并返回只读诊断。

#### Scenario: Build and Verify 使用显式 Codex 目录

- **WHEN** 用户运行打包后的 `build-and-verify doctor --codex` 或 `init --codex` 并传入有效 `--codex-home`
- **THEN** 命令 MUST 把同一目录用于 Codex 子进程和配置读写

#### Scenario: Build and Verify 阻断旧来源

- **WHEN** Codex 仍登记 Legacy MySpec Source 且用户运行 `build-and-verify update`
- **THEN** 命令 MUST 返回非零、不得安装软件包或写入客户端配置，并 MUST 报告 `build-and-verify init --codex`

#### Scenario: Build and Verify 迁移后更新

- **WHEN** 用户完成 `build-and-verify init --codex` 迁移后再次运行 `build-and-verify update`
- **THEN** 命令 MUST 完成稳定来源刷新并返回成功诊断
### Requirement: Build and Verify 支持固定验证基线快速验证
Build and Verify（构建与验证）MUST allow a fast verification command to use an explicit fixed Git（版本管理） baseline and MUST report whether an applicable verification was actually selected.

#### Scenario: Committed changes are selected from a fixed baseline
- **WHEN** a user runs `build-and-verify verify --project <repo> --base <baseline>` in a clean verification worktree（验证工作树）
- **THEN** the system MUST select checks affected by the three-dot difference between `<baseline>` and the current commit of that worktree
- **THEN** commits and uncommitted changes in another worktree MUST NOT affect the selected checks

#### Scenario: Baseline verification rejects an ambiguous input state
- **WHEN** the baseline cannot be resolved, the verification worktree has uncommitted changes, or the user combines `--base` with `--full`
- **THEN** the command MUST return a non-zero exit code and report `status: failed`
- **THEN** the system MUST NOT fall back to worktree change detection or run a different verification mode

#### Scenario: Fast verification reports an empty scope as skipped
- **WHEN** a fixed baseline has no changed files for the current commit
- **THEN** the command MUST report `status: skipped`, `reason: no_changed_files`, and `full-not-run: true`
- **THEN** the command MUST NOT report `status: passed` or run a check

#### Scenario: Fast verification reports unmatched changes as skipped
- **WHEN** a fixed baseline has changed files but no configured check matches them
- **THEN** the command MUST report `status: skipped`, `reason: no_matching_checks`, and `full-not-run: true`
- **THEN** the command MUST NOT report `status: passed` or run full verification

#### Scenario: Selected checks may pass through valid cache hits
- **WHEN** at least one check is selected and every selected check has a valid passed-result cache（通过结果缓存）
- **THEN** the command MUST report `status: passed`
- **THEN** the command MUST report a non-empty `checked` value even when no check process runs
### Requirement: Verification caches are bound to runtime version

Build and Verify（构建与验证） MUST bind fast and full verification cache entries to the current CLI（命令行程序）runtime identity（运行时身份）. In release mode, that identity MUST include the fixed runtime version. In development mode, it MUST use the stable implementation identity exposed by the linked development implementation, so an implementation change invalidates old cache entries even when the package version is unchanged. Configuration, command and cache inputs MUST continue to participate independently in the cache key.

#### Scenario: Released CLI runtime version changes

- **WHEN** the installed released CLI（命令行程序）runtime（运行时）is updated to a different runtime version
- **THEN** fast verify（快速验证） MUST NOT reuse passed-result cache（通过结果缓存） entries from the earlier runtime version
- **THEN** existing cache files MUST NOT require manual deletion

#### Scenario: Development implementation changes without a version change

- **WHEN** the linked development implementation identity changes while its package version remains unchanged
- **THEN** fast verify（快速验证） MUST NOT reuse passed-result cache（通过结果缓存） entries from the earlier implementation
- **THEN** unrelated repository changes that do not affect the Build and Verify implementation MUST NOT change that implementation identity

#### Scenario: Runtime identity remains unchanged

- **WHEN** runtime identity, configuration, command, and cache inputs remain unchanged
- **THEN** fast verify（快速验证） MAY reuse the matching passed-result cache（通过结果缓存）
- **THEN** a configuration, command or input change MUST continue to invalidate cache independently of runtime identity

#### Scenario: Full verification records current runtime identity

- **WHEN** full verify（完整验证） writes passed-result cache（通过结果缓存） entries
- **THEN** those entries MUST use the current released runtime version or development implementation identity

#### Scenario: Runtime identity is missing

- **WHEN** the current runtime identity is absent
- **THEN** fast verify（快速验证） and full verify（完整验证） MUST fail before running checks or reading or writing passed-result cache（通过结果缓存）
- **THEN** build（构建检查） MUST remain available because it does not use verification cache
### Requirement: Build and Verify selects checks by PR scene

Build and Verify（构建与验证） MUST support an explicit `--pr` scene for build（构建） and verify（验证） commands. Each configured check MAY declare boolean `pr`; omission means `true`. Without `--pr`, the existing local selection behavior MUST remain unchanged. With `--pr`, checks with `pr: false` MUST be excluded before path selection, configuration-change selection, scheduling and cache lookup.

#### Scenario: Build selects PR-executable checks

- **WHEN** a user runs `build --pr` with checks marked `pr: false`
- **THEN** the command MUST execute only checks not marked `pr: false`
- **THEN** a build without `--pr` MUST still execute all configured build checks

#### Scenario: Fast verification uses a fixed baseline in PR scene

- **WHEN** a user runs `verify --pr --base <fixed-baseline>`
- **THEN** the command MUST select checks from the PR-executable set using the changed paths from that baseline
- **THEN** a configuration change MUST select all PR-executable checks and MUST NOT reselect `pr: false` checks

#### Scenario: Full verification uses PR-executable checks

- **WHEN** a user runs `verify --pr --full`
- **THEN** the command MUST execute all PR-executable verification checks
- **THEN** `verify --full` without `--pr` MUST still execute all configured verification checks

#### Scenario: Scene and excluded checks are visible

- **WHEN** a build or verify command chooses checks
- **THEN** output MUST identify the run scene and selected checks
- **THEN** PR scene output MUST identify checks excluded by `pr: false`

#### Scenario: No PR check is selected

- **WHEN** PR scene selection produces no checks
- **THEN** the command MUST report `status: skipped` and MUST NOT report `status: passed`
- **THEN** an empty `verify --pr --full` MUST NOT create or overwrite a performance report
- **THEN** a valid passed-result cache hit for a selected check MAY still report `status: passed`

#### Scenario: Invalid PR field stops before scheduling

- **WHEN** any build or verify check declares a non-boolean `pr` value
- **THEN** the command MUST report a configuration error before scheduling any check

#### Scenario: Configuration guidance preserves PR assignment

- **WHEN** initialization or configuration review handles existing checks
- **THEN** it MUST preserve valid `pr` values and explain that omission means `true`
- **THEN** it MUST identify non-boolean values as invalid and describe which checks run in each scene
### Requirement: Local verification shares one enforced invocation budget
Build and Verify（构建与验证） MUST 在明确本机且配置预算的正式验证中缺省强制一次命令的总截止，快速与完整模式共用既有预算字段；独立构建及不同命令调用 MUST NOT 被累计纳入。

#### Scenario: Local verification reaches its deadline
- **WHEN** 明确本机的正式验证开启强制限制且达到总截止
- **THEN** 准备、缓存选择、串行或并行检查、排队、收尾及迁移 MUST 共用该次预算
- **THEN** 系统 MUST 停止后续检查，终止本次拥有的进程及后代，并有界回收
- **THEN** 系统 MUST NOT 终止无关用户进程
- **THEN** 系统 MUST 返回非零总预算超时失败，且单项等待 MUST 受剩余总预算及单项超时中较小值约束

#### Scenario: Execution context is explicit or inherited
- **WHEN** 用户声明 `--execution-context local|cloud|ci`（执行地点：本机、云端、持续集成）或继承 `BUILD_AND_VERIFY_EXECUTION_CONTEXT`（执行地点环境声明）
- **THEN** 命令参数 MUST 优先于环境继承
- **THEN** 拉取请求及可靠持续集成标识 MUST 优先豁免本机强制规则
- **THEN** 系统 MUST NOT 根据模型地点、操作系统或仅有 `CODEX_CI=1`（宿主内部标记）推断持续集成

#### Scenario: Unknown strict context is rejected
- **WHEN** 正式验证执行地点未知且配置预算、强制开启
- **THEN** 系统 MUST 在启动检查前明确拒绝
- **THEN** 系统 MUST NOT 静默豁免或伪报本机

#### Scenario: Passed cache remains truthful
- **WHEN** 本机验证复用或更新通过缓存
- **THEN** 快速模式 MUST 仅复用输入、配置、命令和运行身份匹配的成功结果
- **THEN** 完整模式 MUST NOT 读取成功缓存跳过检查
- **THEN** 超时、取消和未启动 MUST NOT 写成功缓存；截止前真实完成的成功检查 MAY（可以）缓存
### Requirement: One-shot diagnostic preserves real failures without formal acceptance
Build and Verify（构建与验证） MUST 提供 `--diagnostic`（一次性诊断），仅取消本次总截止，不改变项目配置或正式验收语义。

#### Scenario: Diagnostic runs beyond the total budget
- **WHEN** 用户启用一次性诊断
- **THEN** 系统 MUST 保留单项防挂超时、真实检查失败及异常
- **THEN** 系统 MUST 实时输出检查开始、结束、耗时及未完成状态
- **THEN** 系统 MUST 明确标记诊断结果不构成正式预算通过，且 MUST NOT 写入正式成功缓存

#### Scenario: Diagnostic observes individual test costs
- **WHEN** 用户定位单项测试或子测试耗时
- **THEN** 插件文档 MUST 引导使用测试框架原生选择及计时能力
- **THEN** 插件 MUST NOT 宣称拥有新增检查选择器或可解析所有业务子测试
### Requirement: Build and Verify 生命周期只支持 Claude 和 Codex

Build and Verify（构建与验证）MUST 保留 Claude/Codex（编码助手/代码代理）的初始化、来源诊断、更新、有效状态恢复和旧来源保护；生命周期命令 MUST 不安装或调用 Pi（编码助手），且 MUST 拒绝已撤除的 Pi 客户端选择参数。通用 Node.js（脚本运行时）和 Python（工具实现语言）构建验证能力 MUST 保持可用。

#### Scenario: 默认诊断工具自身

- **WHEN** 用户不带客户端选择参数运行 `build-and-verify doctor`
- **THEN** 命令 MUST 只报告工具包、工具链身份和安装操作状态，且不得要求客户端配置目录可用
- **THEN** 命令 MUST NOT 查询 Claude、Codex 或 Pi

#### Scenario: 显式诊断全部受支持客户端

- **WHEN** 用户运行 `build-and-verify doctor --all` 或 `init --all`
- **THEN** 客户端结果 MUST 只包含 Claude 和 Codex，并保留不可用客户端的既有报告行为

#### Scenario: Build and Verify 旧未完成记录包含 Pi

- **WHEN** 已保存的未完成更新记录把 Pi 列为待刷新客户端
- **THEN** `build-and-verify update` MUST 复用 `invalid_update_state`（更新状态无效）失败路径，在 npm（软件包管理器）安装和客户端刷新前停止
- **THEN** 原更新记录和旧 Pi 配置 MUST 保持不变，不得重新安装 Pi、自动迁移或跳过未完成步骤
- **THEN** `build-and-verify doctor` MUST 能只读展示该未完成记录
