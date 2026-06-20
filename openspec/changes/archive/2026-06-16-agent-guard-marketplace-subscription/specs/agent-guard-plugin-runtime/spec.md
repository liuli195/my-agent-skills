## ADDED Requirements

### Requirement: Marketplace 订阅入口
系统 MUST 支持通过 marketplace subscription（市场订阅）发布和验证 Agent Guard Plugin（代理守卫插件），并覆盖 personal marketplace（个人市场）和 repo marketplace（仓库市场）。

#### Scenario: 个人市场条目
- **WHEN** installer（安装器）为 personal scope（个人作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用 personal marketplace（个人市场）位置，并把 `agent-guard` 条目解析为 personal plugin package（个人插件包）

#### Scenario: 仓库市场条目
- **WHEN** installer（安装器）为 repo scope（仓库作用域）执行 dry-run（试运行）、install（安装）或 verify（验证）
- **THEN** 它使用当前仓库的 Codex `.agents/plugins/marketplace.json` 和 Claude `.claude-plugin/marketplace.json`，并把 `agent-guard` 条目解析为 `./plugins/agent-guard`

#### Scenario: GitHub 发布分支订阅
- **WHEN** 生成或验证正式 marketplace subscription（市场订阅）说明
- **THEN** 订阅源指向 GitHub repo（GitHub 仓库）的 `marketplace` 发布分支，不使用 tag（标签）或 commit（提交）固定版本

### Requirement: Marketplace 条目契约
系统 MUST 为 Agent Guard Plugin（代理守卫插件）生成和验证包含 `source`、`policy` 和 `category` 的 marketplace entry（市场条目）。

#### Scenario: 生成 Codex 本地条目
- **WHEN** installer（安装器）写入 marketplace entry（市场条目）
- **THEN** 条目包含 `name: agent-guard`、`source.source: local`、`source.path: ./plugins/agent-guard`、`policy.installation`、`policy.authentication` 和 `category`

#### Scenario: 生成 Claude 仓库目录
- **WHEN** installer（安装器）写入 Claude repo marketplace catalog（仓库市场目录）
- **THEN** `.claude-plugin/marketplace.json` 包含 `agent-guard` 插件条目，并把插件目录解析到 `plugins/agent-guard`

#### Scenario: 验证条目
- **WHEN** installer（安装器）验证 marketplace entry（市场条目）
- **THEN** 它拒绝缺少 `source` 对象、`policy.installation`、`policy.authentication` 或 `category` 的旧格式条目

### Requirement: 插件包自包含
系统 MUST 让 `plugins/agent-guard` 成为 Codex 和 Claude 都可安装的自包含 plugin package（插件包）。

#### Scenario: 自包含资源
- **WHEN** package verification（包验证）检查 Agent Guard Plugin（代理守卫插件）
- **THEN** skills（技能）、hooks（钩子）、runtime（运行时）、scripts（脚本）、assets（资源）以及 `.codex-plugin/plugin.json` 和 `.claude-plugin/plugin.json` 都位于 `plugins/agent-guard` 内

## MODIFIED Requirements

### Requirement: 授权插件安装器
系统 MUST 让插件安装保持显式、目标明确、可验证，并以 dry-run（试运行）作为安全默认行为。

#### Scenario: 试运行
- **WHEN** installer（安装器）在没有 install authorization（安装授权）的情况下被调用
- **THEN** 它报告计划写入或验证的 Codex 和 Claude plugin package（插件包）位置、personal marketplace（个人市场）位置和 repo marketplace（仓库市场）位置，不修改 user-level plugin locations（用户级插件位置）或 marketplace files（市场文件）

#### Scenario: 授权安装
- **WHEN** installer（安装器）收到明确 target（目标）、scope（作用域）和 install authorization（安装授权）
- **THEN** 它安装或更新对应 plugin package（插件包）和 marketplace entry（市场条目），并可以验证 manifest（清单）、hook（钩子）、runtime（运行时）、Skill（技能）入口和 marketplace entry（市场条目）可用

#### Scenario: 产品目标校验
- **WHEN** installer（安装器）以 `target: codex`、`target: claude` 或 `target: all` 运行
- **THEN** 它分别校验 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` 或两者，并且不把 Claude Junction（Claude 目录联接）作为兼容条件

#### Scenario: 作用域校验
- **WHEN** installer（安装器）以 `scope: personal`、`scope: repo` 或 `scope: all` 运行
- **THEN** 它分别验证 personal marketplace（个人市场）、repo marketplace（仓库市场）或两者，并且不写入 Guard Profile（守卫画像）、project hooks（项目钩子）或 git config（Git 配置）
