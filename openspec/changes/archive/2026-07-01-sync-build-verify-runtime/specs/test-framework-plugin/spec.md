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

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.build-and-verify/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.build-and-verify/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json`、`.build-and-verify/.gitignore` 或 `.build-and-verify/runtime/`
- **THEN** 系统 MUST 在写入任何初始化产物前拒绝静默覆盖
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

### Requirement: Build and Verify has no root-level Python test configuration dependency
系统 MUST 不依赖根目录 Python（Python 语言）测试配置来定义本仓库 build（构建检查）或 verify（验证）行为。

#### Scenario: Root pyproject test config is absent
- **WHEN** 本仓库 build-and-verify（构建与验证）配置完成迁移
- **THEN** 根目录 `pyproject.toml` MUST NOT 存在
- **THEN** `.build-and-verify/config.json` 中的 pytest（Python 测试运行器）命令 MUST 显式声明测试路径和所需命令参数

#### Scenario: No root wrapper entrypoint
- **WHEN** 本仓库活跃自动化和 guard（守卫）命令文件被检查
- **THEN** 它们 MUST NOT 引用根目录测试 wrapper（包装入口）
- **THEN** 它们 MUST 引用仓库内 `.build-and-verify/runtime/build_and_verify.py` 或当前安装的 build-and-verify（构建与验证）Skill（技能）脚本

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
- **WHEN** 用户运行 `python <build-and-verify-script> init --project <repo>`
- **THEN** 系统 MUST 创建空的 `.build-and-verify/config.json`（配置文件）模板
- **THEN** 系统 MUST 复制当前 runtime（运行时）快照到 `.build-and-verify/runtime/`
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中执行对话式问答
- **THEN** 系统 MUST NOT 在命令行 init（初始化）中自动生成仓库业务检查项
