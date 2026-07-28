## MODIFIED Requirements

### Requirement: Build and Verify initializes standard artifacts
系统 MUST 为目标仓库初始化最小构建检查、验证配置和仓库内 runtime（运行时）入口结构。

#### Scenario: Init creates standard files
- **WHEN** 用户对目标仓库运行 build-and-verify init（构建与验证初始化）
- **THEN** 系统 MUST 创建 `.build-and-verify/config.json`
- **THEN** 系统 MUST 创建 `.build-and-verify/.gitignore`
- **THEN** `.build-and-verify/.gitignore` MUST 包含 `/cache/`、`/runs/` 和 `/backups/`
- **THEN** 系统 MUST 复制当前 runtime（运行时）快照到 `.build-and-verify/runtime/`
- **THEN** 仓库内 runtime（运行时）快照 MUST 包含 `build_and_verify.py`、`build_and_verify_runner.py` 和版本元数据

#### Scenario: Init writes confirmed config when provided
- **WHEN** 用户运行 `python <build-and-verify-script> init --project <repo> --config <config-file> --overwrite`
- **THEN** 系统 MUST 使用 `<config-file>` 内容写入 `.build-and-verify/config.json`
- **THEN** 系统 MUST 在已有 `.build-and-verify/config.json` 时先备份到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`
- **THEN** 系统 MUST 在没有已有 `.build-and-verify/config.json` 时直接写入 confirmed config（已确认配置）
- **THEN** 系统 MUST 合并 `.build-and-verify/.gitignore` 默认规则而不是覆盖用户已有规则
- **THEN** 系统 MUST 复制当前 runtime（运行时）快照到 `.build-and-verify/runtime/`

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.build-and-verify/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.build-and-verify/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files without overwrite
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json`、`.build-and-verify/.gitignore` 或 `.build-and-verify/runtime/`
- **THEN** 系统 MUST 在没有 `--overwrite`（覆盖参数）时拒绝静默覆盖
- **THEN** 系统 MUST 返回 non-zero（非零）退出码并报告 target-repository-relative（目标仓库相对）冲突路径

#### Scenario: Init stays uncoupled from repository business logic
- **WHEN** 插件初始化目标仓库
- **THEN** 模板 MUST NOT 内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或任一具体仓库业务检查
- **THEN** 仓库业务检查 MUST 只通过 `.build-and-verify/config.json` 声明

### Requirement: Build and Verify provides unified configuration and commands
系统 MUST 通过一个配置文件和同一套 runtime（运行时）命令入口表达 build（构建检查）与 verify（验证）行为。

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
- **THEN** `python <build-and-verify-script> build --project <repo>` MUST 运行 configured `build.checks`
- **THEN** `python <build-and-verify-script> verify --project <repo>` MUST 运行默认 fast（快速验证）执行模式
- **THEN** `python <build-and-verify-script> verify --project <repo> --full` MUST 运行完整 `verify.checks`
- **THEN** `python <build-and-verify-script> update-runtime --project <repo>` MUST 显式刷新 `.build-and-verify/runtime/`
- **THEN** `<build-and-verify-script>` MUST 支持当前安装的 user-level（用户级）Skill（技能）脚本路径和仓库内 `.build-and-verify/runtime/build_and_verify.py` 路径

#### Scenario: Update runtime copies the executing runtime
- **WHEN** 用户运行 `python <build-and-verify-script> update-runtime --project <repo>`
- **THEN** 系统 MUST 从 `<build-and-verify-script>` 所在 runtime（运行时）目录复制 `build_and_verify.py`、`build_and_verify_runner.py` 和版本元数据
- **THEN** 系统 MUST NOT 从隐式用户级路径自动选择其他复制来源
- **THEN** 系统 MUST NOT 修改 `.build-and-verify/config.json`

#### Scenario: Repository runtime reports newer installed runtime without mutating files
- **WHEN** 用户运行仓库内 `python .build-and-verify/runtime/build_and_verify.py build --project <repo>` 或 `python .build-and-verify/runtime/build_and_verify.py verify --project <repo>`
- **THEN** 系统 MUST 尽力比较仓库内 runtime（运行时）版本与可发现的 Codex（代码助手）或 Claude（Claude 版本）user-level（用户级）runtime（运行时）版本
- **THEN** user-level（用户级）runtime（运行时）版本领先时，系统 MUST 输出使用该新版脚本运行 `update-runtime`（更新运行时）的提示
- **THEN** user-level（用户级）runtime（运行时）不可发现时，系统 MUST 静默继续运行原命令
- **THEN** build（构建）和 verify（验证）命令 MUST NOT 自动修改 `.build-and-verify/runtime/`

#### Scenario: Full verify refreshes passed cache
- **WHEN** 用户运行 `python <build-and-verify-script> verify --project <repo> --full`
- **THEN** 系统 MUST NOT 通过读取 cache（缓存）跳过 configured `verify.checks`
- **THEN** 成功通过的 check（检查项） MUST 使用同一套 cache key（缓存键）写入或刷新 passed-result cache（通过结果缓存）
- **THEN** failed（失败）结果 MUST NOT 写入 passed-result cache（通过结果缓存）

#### Scenario: Pytest xdist workers are explicit
- **WHEN** check（检查项）配置声明 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** `pytestXdistWorkers` MUST 是 `"auto"` 或正整数
- **THEN** 系统 MUST 仅对 pytest（Python 测试框架）命令应用 pytest-xdist（Pytest 并行插件）参数
- **THEN** 系统 MUST 拒绝在非 pytest（Python 测试框架）命令上声明 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** 系统 MUST 在 pytest-xdist（Pytest 并行插件）不可用时报错，不得静默降级为串行

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
- **WHEN** 目标仓库包含 `Makefile`（任务文件）、`scripts/`（脚本目录）、`tests/`（测试目录）或 `openspec/`（开放规格目录）等通用信号
- **THEN** agent（代理） MUST 分类候选 checks（检查项），并展示 source（来源）、confidence（置信度）、reason（纳入理由）和 risk（风险提示）
- **THEN** agent（代理） MUST NOT 运行候选 command（命令）
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
