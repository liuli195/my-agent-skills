# MySpec Distribution

## Purpose

本 capability（能力）定义 MySpec（自有规格）统一 npm（软件包管理器）发行包、机器级模式、三类 Agent（代理）集成、诊断更新与发布验证行为。

## Requirements

### Requirement: MySpec 以单一 npm 包提供完整用户入口

系统 MUST 通过 `@liuli195/myspec` 单一 npm（软件包管理器）包提供 `myspec` CLI（命令行程序）、四个 Skill（技能）以及 Pi、Claude 和 Codex 所需资源，并保持既有规格业务子命令、参数、标准流和退出码行为。

#### Scenario: 用户安装发布包

- **WHEN** 用户安装 `@liuli195/myspec`
- **THEN** 安装后的 `myspec` MUST 可运行全部既有规格业务子命令
- **THEN** 同一包 MUST 包含 Pi、Claude 和 Codex 可发现的四个 MySpec Skill（技能）
### Requirement: MySpec 启动器确定性选择 Python

系统 MUST 让启动器相对于已安装包定位唯一 Python（脚本语言）核心，依次尝试 `MYSPEC_PYTHON`、`python3.12`、`python3`、`python` 和 Windows `py -3.12`，只接受 Python 3.12 或更高版本，并完整转发参数、标准流、信号和退出码。

#### Scenario: 环境存在多个 Python 候选

- **WHEN** 用户运行 `myspec` 且多个候选解释器可用
- **THEN** 启动器 MUST 使用第一个版本不低于 3.12 的候选

#### Scenario: 环境没有合格 Python

- **WHEN** 所有解释器候选均缺失或版本低于 3.12
- **THEN** `myspec` MUST 返回清晰的非零诊断
- **THEN** 系统 MUST NOT 自动安装 Python 或降级运行
### Requirement: MySpec 模式切换保持机器级单一来源

系统 MUST 让 `myspec init --dev` 和 `myspec init --release` 显式切换机器级 MySpec 模式，使 CLI（命令行程序）与所有已安装 Agent（代理）始终解析同一个全局 npm 包稳定目录。

#### Scenario: 用户进入开发模式

- **WHEN** 用户运行 `myspec init --dev` 并提供有效源码目录，或在有效源码目录中省略该参数
- **THEN** 系统 MUST 保存当前发布版本和源码身份，并通过 npm Link（npm 本地链接）让源码修改在下一次命令或 Agent 重新加载后可见
- **THEN** 系统 MUST NOT 搜索父目录或猜测其他检出目录

#### Scenario: 用户恢复发布模式

- **WHEN** 用户运行 `myspec init --release`
- **THEN** 系统 MUST 恢复进入开发模式前保存的固定发布版本且不得隐式升级
- **THEN** 缺少已保存发布版本时系统 MUST 停止并返回非零结果
### Requirement: MySpec 初始化三类 Agent 的统一来源

系统 MUST 通过 `myspec init --pi`、`--claude`、`--codex` 或 `--all` 初始化对应 Agent（代理）；Pi MUST 登记全局 npm 包稳定目录，Claude 和 Codex MUST 登记包内自包含单插件市场。

#### Scenario: 用户显式初始化一个不可用的 Agent

- **WHEN** 用户显式选择的 Pi、Claude 或 Codex 不可用
- **THEN** 初始化 MUST 失败且不得安装该 Agent

#### Scenario: 用户初始化所有 Agent

- **WHEN** 用户运行 `myspec init --all`
- **THEN** `--all` MUST 只包含 Pi、Claude 和 Codex
- **THEN** 系统 MUST 跳过并报告不可用客户端，且继续初始化其他可用客户端

#### Scenario: 初始化发现旧 MySpec 来源

- **WHEN** 新统一来源已启用且 Agent 中存在旧远端或旧源码 MySpec 来源
- **THEN** 系统 MUST 禁用重复的旧 MySpec 来源
- **THEN** 系统 MUST NOT 删除插件、市场、缓存目录、市场订阅或用户文件
### Requirement: MySpec doctor 只读诊断真实安装状态

系统 MUST 让 `myspec doctor` 从 npm（软件包管理器）和真实 Agent（代理）客户端查询模式、来源、版本、启用状态、重复来源、锁、部分操作和重新加载要求，且不得依赖平行保存的安装清单。

#### Scenario: 用户运行诊断

- **WHEN** 用户运行 `myspec doctor` 并选择一个客户端或全部客户端
- **THEN** 命令 MUST 报告实际安装状态和版本失配
- **THEN** 命令 MUST NOT 修改插件、市场、模式、锁或用户文件
### Requirement: MySpec update 统一更新发布模式安装

系统 MUST 让 `myspec update` 只在发布模式解析 npm 最新版本、预检已安装客户端、更新全局包、由新 CLI（命令行程序）继续刷新全部已安装 Agent（代理），并在结束时运行只读诊断。

#### Scenario: 开发模式请求更新

- **WHEN** 用户在开发模式运行 `myspec update`
- **THEN** 命令 MUST 返回非零结果并要求用户先显式切换发布模式
- **THEN** 命令 MUST NOT 隐式改变模式

#### Scenario: 发布模式请求更新

- **WHEN** 用户在发布模式运行 `myspec update`
- **THEN** CLI（命令行程序）和所有已安装 MySpec 插件 MUST 最终使用同一 npm 最新版本
### Requirement: MySpec 安装操作可串行且可继续

系统 MUST 让 `init` 与 `update` 共用用户级安装锁，并把外部修改记录为可重复执行的幂等步骤；失败必须立即停止并保留原始错误，不承诺跨客户端自动回滚。

#### Scenario: 安装操作并发运行

- **WHEN** 新操作发现记录进程仍存在的安装锁
- **THEN** 系统 MUST 拒绝并发修改
- **THEN** 系统 MUST NOT 仅因锁经过一段时间而回收它

#### Scenario: 安装操作中断后重试

- **WHEN** 用户重复运行先前中断的相同操作
- **THEN** 系统 MUST 跳过已确认完成的步骤并继续收敛
- **THEN** 只有记录进程已被证明不存在时系统 MAY 回收遗留锁
### Requirement: MySpec 发布验证使用当前检出的真实包

系统 MUST 让完整本地验证与 PR CI（拉取请求持续集成）从当前检出生成同一 npm Tarball（npm 软件包），在隔离环境安装后通过用户入口验证完整业务流程；发布流程只能在该发布形态验证通过后发布同版本 npm 包、Git Tag（Git 标签）和 GitHub Release（发布版本）。

#### Scenario: 贡献者运行完整验证或 PR CI

- **WHEN** 当前检出的 MySpec 变更接受完整验证
- **THEN** 验证 MUST 安装并调用当前检出生成的 Tarball（npm 软件包）
- **THEN** 验证 MUST NOT 使用机器预装版、npm 最新发布版或上一发布版代替当前检出

#### Scenario: 维护者发布 MySpec

- **WHEN** 候选包的源码测试和打包后端到端流程均通过
- **THEN** 发布流程 MUST 发布版本一致的 npm 包、Git Tag（Git 标签）和 GitHub Release（发布版本）记录
- **THEN** 发布流程 MUST NOT 生成 Wheel（Python 安装包）、Pi ZIP（Pi 压缩包）或自建发布资产缓存
