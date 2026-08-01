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
### Requirement: MySpec update 统一更新发布模式安装

系统 MUST 让 `myspec update` 只在发布模式解析 npm 最新版本、预检已安装客户端、更新全局包、由新 CLI（命令行程序）继续刷新全部已安装 Agent（代理），并在结束时运行只读诊断。更新前后 MUST 使用一致的规范化来源判据验证客户端状态。

#### Scenario: 开发模式请求更新

- **WHEN** 用户在开发模式运行 `myspec update`
- **THEN** 命令 MUST 返回非零结果并要求用户先显式切换发布模式
- **THEN** 命令 MUST NOT 隐式改变模式

#### Scenario: 发布模式请求更新

- **WHEN** 用户在发布模式运行 `myspec update`
- **THEN** CLI（命令行程序）和所有已安装 MySpec 插件 MUST 最终使用同一 npm 最新版本

#### Scenario: 更新保留客户端来源状态

- **WHEN** 更新流程保存并验证 Pi、Claude 或 Codex 的来源状态
- **THEN** Claude 和 Codex MUST 按稳定来源的配置启用状态验证恢复结果
- **THEN** Pi MUST 按考虑受信任项目覆盖后的稳定来源实际生效状态验证恢复结果
- **THEN** 更新流程 MUST NOT 把汇总顶层启用状态误作单个稳定来源状态
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

- **WHEN** 新统一来源已启用并验证，且 Agent 中存在 Legacy MySpec Source（旧 MySpec 来源）
- **THEN** 系统 MUST 精确移除用户级旧 MySpec 来源或旧插件记录
- **THEN** Pi 项目级旧来源 MUST 保留并禁用，不得删除项目配置
- **THEN** Claude MUST 在卸载旧插件时保留该插件的持久数据
- **THEN** 系统 MUST NOT 删除共享市场、市场订阅、无关插件、源码目录或用户文件

#### Scenario: 初始化未发现旧 MySpec 来源

- **WHEN** 对应 Agent 不存在 Legacy MySpec Source（旧 MySpec 来源）
- **THEN** 初始化 MUST 成功且不得调用旧来源删除命令
- **THEN** 重复初始化 MUST 保持幂等

#### Scenario: 初始化报告旧来源处理结果

- **WHEN** 单客户端初始化或 `myspec init --all` 完成
- **THEN** Pi 结果 MUST 通过 `removedLegacySources` 和 `disabledProjectLegacySources` 分别报告已删除用户来源和已禁用项目来源
- **THEN** Claude 和 Codex 结果 MUST 通过 `removedLegacyPlugins` 报告已删除旧插件
- **THEN** 没有对应处理结果时字段 MUST 返回空数组
### Requirement: MySpec doctor 只读诊断真实安装状态

系统 MUST 让 `myspec doctor` 从 npm（软件包管理器）和真实 Agent（代理）客户端查询模式、来源、版本、启用状态、重复来源、锁、部分操作和重新加载要求，且不得依赖平行保存的安装清单。Pi、Claude 和 Codex MUST 使用一致的来源状态语义，并在保留既有顶层字段的同时公开规范化来源记录。

#### Scenario: 用户运行诊断

- **WHEN** 用户运行 `myspec doctor` 并选择一个客户端或全部客户端
- **THEN** 命令 MUST 报告实际安装状态和版本失配
- **THEN** 命令 MUST NOT 修改插件、市场、模式、锁或用户文件

#### Scenario: 三类客户端报告规范化来源

- **WHEN** Pi、Claude 或 Codex 报告一个 MySpec 来源
- **THEN** 每条来源记录 MUST 分别报告 `installed`、`registered`、`enabled`、`effective`、`sourceKind` 和 `sourceMismatch`
- **THEN** `installed` MUST 只在宿主报告安装位置且该位置包含可识别 MySpec 包时为真
- **THEN** `registered` MUST 只表示宿主已经识别并登记该来源，不得从安装或启用状态推导
- **THEN** `enabled` MUST 表示公开配置允许加载该来源，并与安装目录或技能文件是否存在相互独立
- **THEN** `effective` MUST 只在来源已登记、已安装、已启用且未被更高优先级来源覆盖时为真

#### Scenario: 诊断区分稳定、旧版和错误来源

- **WHEN** 诊断识别 MySpec 稳定来源或旧版来源
- **THEN** `sourceKind` MUST 分别报告 `stable` 或 `legacy`
- **THEN** 旧版来源 MUST NOT 仅因其为旧版而报告来源不匹配
- **WHEN** 规范目标标识解析到不同来源
- **THEN** `sourceMismatch` MUST 为真，且错误来源 MUST NOT 实际生效
- **THEN** 无关来源 MUST NOT 进入 MySpec 来源列表

#### Scenario: 共享市场不构成旧来源

- **WHEN** Claude 或 Codex 仍登记共享市场，但该市场的旧 MySpec 插件记录不存在
- **THEN** 诊断 MUST NOT 创建 Legacy MySpec Source（旧 MySpec 来源）记录或报告第二个已安装来源
- **THEN** 共享市场 MUST 继续保留并可提供其他插件

#### Scenario: 缺失安装仍保留配置事实

- **WHEN** 宿主已登记并启用 MySpec 来源但安装目录缺失
- **THEN** 诊断 MUST 保持 `registered` 和 `enabled` 为真
- **THEN** 诊断 MUST 报告 `installed` 和 `effective` 为假

#### Scenario: Pi 来源遵守过滤与项目优先级

- **WHEN** Pi 用户配置或项目配置使用公开来源过滤规则
- **THEN** 诊断 MUST 仅在规则允许至少一个 MySpec 技能时报告来源已启用
- **THEN** 相对路径 MUST 以拥有该路径的设置文件为基准解析
- **THEN** 受信任项目来源 MUST 按项目优先级决定实际生效状态

#### Scenario: 顶层兼容字段与来源记录一致

- **WHEN** 诊断同时返回既有顶层字段和规范化来源记录
- **THEN** 既有顶层字段 MUST 保留
- **THEN** 顶层启用状态和启用来源投影 MUST NOT 与规范化来源记录矛盾
