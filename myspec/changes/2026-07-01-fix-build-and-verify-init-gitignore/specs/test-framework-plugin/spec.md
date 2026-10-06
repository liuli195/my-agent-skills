## MODIFIED Requirements

### Requirement: Build and Verify initializes standard artifacts
系统 MUST 为目标仓库初始化最小构建检查和验证产物结构。

#### Scenario: Init creates standard files
- **WHEN** 用户对目标仓库运行 build-and-verify init（构建与验证初始化）
- **THEN** 系统 MUST 创建 `.build-and-verify/config.json`
- **THEN** 系统 MUST 创建 `.build-and-verify/.gitignore`
- **THEN** `.build-and-verify/.gitignore` MUST 包含 `/cache/`、`/runs/` 和 `/backups/`
- **THEN** 系统 MUST NOT 向目标仓库复制 runner（运行器）脚本

#### Scenario: Init defines local cache location
- **WHEN** 初始化产物写入目标仓库
- **THEN** 系统 MUST 使用 `.build-and-verify/cache/` 作为本地 cache（缓存）目录
- **THEN** 系统 MUST 创建 `.build-and-verify/cache/` 目录
- **THEN** 系统 MUST NOT 要求将 cache（缓存）内容纳入 Git（版本管理）

#### Scenario: Init refuses conflicting files
- **WHEN** 目标仓库已经存在 `.build-and-verify/config.json` 或 `.build-and-verify/.gitignore`
- **THEN** 系统 MUST 在写入任何初始化产物前拒绝静默覆盖
- **THEN** 系统 MUST 返回 non-zero（非零）退出码并报告 target-repository-relative（目标仓库相对）冲突路径

#### Scenario: Init stays uncoupled from repository business logic
- **WHEN** 插件初始化目标仓库
- **THEN** 模板 MUST NOT 内置 PR Flow（拉取请求流程）、Release Flow（发布流程）、Comet（双星流程）或任一具体仓库业务检查
- **THEN** 仓库业务检查 MUST 只通过 `.build-and-verify/config.json` 声明

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
- **THEN** 命令包含 `pytest -n` 或 `--numprocesses` 时，agent（代理） MUST 检查 `pytest-xdist`（Pytest 并行插件）是否可用
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
