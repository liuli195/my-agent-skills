# plugin-sync-runtime-sync Specification

## Purpose

TBD - created by archiving change stabilize-version-runtime-sync. Update Purpose after archive.

## Requirements

### Requirement: Plugin Sync delegates MySpec lifecycle management

Plugin Sync（插件同步）MUST 将 MySpec（自有规格）的初始化、诊断、机器级模式切换和更新委托给 `myspec` CLI（命令行程序），不得复制 MySpec 的路径、市场、模式或版本规则。

#### Scenario: 用户通过 Plugin Sync 管理 MySpec

- **WHEN** 用户要求 Plugin Sync 检查、初始化、切换或更新 MySpec
- **THEN** Plugin Sync MUST 调用适用的 `myspec init`、`myspec doctor` 或 `myspec update`
- **THEN** Plugin Sync MUST NOT 自行推断 MySpec 的包路径、客户端市场、模式或目标版本
### Requirement: Plugin Sync delegates Build and Verify lifecycle management
Plugin Sync（插件同步）MUST 将 Build and Verify（构建与验证）的诊断、初始化和更新委托给 `build-and-verify` CLI（命令行程序），不得维护或同步目标仓库的运行时快照。

#### Scenario: 用户通过 Plugin Sync 管理 Build and Verify
- **WHEN** 用户要求 Plugin Sync 检查、初始化或更新 Build and Verify
- **THEN** Plugin Sync MUST 调用适用的 `build-and-verify doctor`、`build-and-verify init` 或 `build-and-verify update`
- **THEN** Plugin Sync MUST NOT 读取、刷新、提交或报告 `.build-and-verify/runtime/`
### Requirement: Plugin Sync switches one marketplace plugin with native client evidence

Plugin Sync（插件同步）MUST 在用户授权后通过客户端原生操作逐插件切换开发与正式来源，先核对目标和原安装状态，使用完整插件加市场标识；Claude（代码助手）保留原安装范围。切换前后 MUST 核对两个市场、其他插件、实际来源、版本、启用及资源内容。开发修改后按客户端刷新和会话重新加载步骤生效，不把安装或文件可读当作新会话已执行。

#### Scenario: A user switches an installed plugin

- **WHEN** 用户明确选择目标插件与新来源
- **THEN** 同一客户端按完整标识串行切换，两个市场和无关插件保留
- **THEN** 实际来源及资源核对通过才报告已安装；运行中的代理及业务工具需要重新加载时明确提示
### Requirement: Plugin Sync reports failed switches and restores recorded sources accurately

Plugin Sync MUST 对目标缺失、重复来源、安装失败及恢复失败分别报告，保留本次操作的真实错误与可用恢复动作；恢复时核对实际版本，不声称已恢复不可取得的旧版本。数据中心来源变化时 MUST 检查并更新用户明确接入的项目关系，不通过全盘扫描寻找仓库，不另建定位程序或长期安装清单。

#### Scenario: Installation or restoration fails

- **WHEN** 目标不可用、安装失败或恢复原来源失败
- **THEN** 工具保留准确状态和错误，明确已完成步骤与下一动作，不报告完整成功
- **THEN** 未完成项目更新或需要重启时明确列出，不删除源码、用户数据或无关安装
### Requirement: Plugin Sync preserves local markets and orchestrates official account delivery

Plugin Sync  MUST 保留本机正式/开发双市场及完整来源隔离，同时通过宿主官方Creator作为唯一个人账号内容创建更新入口；客户端安装卸载使用各端实际官方能力。

#### Scenario: Observable outcome

- **WHEN** 交付正式归档或切换来源
- **THEN** 创建、保存、安装、发现、运行分别记录；无能力或未知结果停止，不混用原生内容发布API。
### Requirement: Creator synchronization preserves identity and recoverability

同步  MUST 先核对个人USER/PRIVATE上下文、精确对象与release标识、正式来源和完整文件；更新只删除已知旧受管文件，拒绝同版本不同内容和未知或冲突覆盖。操作发送前记录计划，失败保留原回执。

#### Scenario: Observable outcome

- **WHEN** 创建或更新个人正式对象
- **THEN** 单次写入后只读核验；未知只读恢复、不重放；自更新最后执行并由新会话验证。
### Requirement: Private adaptation and official discovery remain separate

dot与本机Codex  MUST 核对同一私人适配对象和版本；配置授权的调用元数据允许隐式调用但不保证模型选择。Claude  MUST 使用官方市场原版，版本或内容与批准目标不符即停止该端迁移并请用户决定。

#### Scenario: Observable outcome

- **WHEN** 宿主发现或回退读取第三方技能
- **THEN** 原生发现优先，只有核验可读的官方目录才可文件回退；访问拒绝或资源缺失不绕过。
### Requirement: Creator delivery audits explicitly accepted wrapper metadata

Plugin Sync MUST 默认逐文件严格核对正式来源与官方实际内容。仅已有成功创建操作在用户明确接受具体包装作者信息差异后，允许通过原记录入口离线结案；仅允许作者名称、作者邮箱及开发者名称的精确增加或替换，不删除字段或接受其他差异。MUST 绑定原操作、计划、正式归档摘要、对象、版本、远端发布及官方个人 USER/PRIVATE 归属证据，并保留原计划、原回执、来源及实际摘要与接受依据，不把该结论表述为全部字节一致或已安装、发现、运行。

#### Scenario: An accepted creation is reconciled without another account write

- **WHEN** 原始成功创建回执、完整官方读回及用户接受的精确旧新值均与同一来源和发布匹配
- **THEN** 仅离线恢复该记录，保留全部证据；文件集合及其他文件字节摘要必须一致，包装清单除获准字段外语义一致，两个原始清单文本各自摘要匹配来源及实际文件
- **THEN** 不发送账号写请求，不重复创建、上传或安装

#### Scenario: Missing or conflicting evidence remains blocked

- **WHEN** 接受证据缺失、身份或来源漂移、重复 JSON 键、未获准字段变化、其他文件改变或结果未知
- **THEN** 拒绝接受模式，不新建待发送记录、不改写既有回执或清除未决证据

#### Scenario: A subsequent unchanged request reuses only the same verified result

- **WHEN** 后续请求归档摘要、来源文件、实际文件、对象、版本和远端发布均与已核验记录相同
- **THEN** 可报告无变化；不同归档、发布或新增差异不能继承旧接受结论，未来更新仍遵循原完整文件和删除规则
