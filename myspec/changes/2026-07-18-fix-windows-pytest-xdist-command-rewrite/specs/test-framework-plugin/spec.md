## MODIFIED Requirements

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
- **THEN** 对字符串命令应用 pytest-xdist（Pytest 并行插件）参数时，系统 MUST 保留原命令的 shell（命令行解释器）语法、路径和引号
- **THEN** 系统 MUST 拒绝在非 pytest（Python 测试框架）命令上声明 `pytestXdistWorkers`（Pytest 工作进程数）
- **THEN** 系统 MUST 在 pytest-xdist（Pytest 并行插件）不可用时报错，不得静默降级为串行
