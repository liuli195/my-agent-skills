# awehitch-local-patches Specification

## Purpose

让第三方包 awehitch 升级后先接受真实入口验证，只重放仍有失败证据且收益合理的本地修复；避免旧补丁凭静态猜测污染新版本。

## Requirements

### Requirement: 先升级实测，再准入补丁

系统 MUST 先安装未打本地补丁的目标版本并逐项运行真实行为测试。只有在该干净版本上稳定复现原始症状的补丁，才可加入 `scripts/awehitch-local-patches.ps1`。版本发布说明、源码相似或静态特征 MUST NOT 单独作为保留补丁的依据。

#### Scenario: 新版本发布

- **WHEN** 开发者准备升级 awehitch
- **THEN** 开发者 MUST 先备份当前安装、配置和状态
- **THEN** 开发者 MUST 安装干净新版本并完成逐项实测
- **THEN** 开发者 MUST NOT 在首轮实测前运行或修改旧补丁脚本

#### Scenario: 旧问题未复现

- **WHEN** 干净新版本的真实入口不能复现某个旧问题
- **THEN** 该补丁 MUST NOT 在新版本上重放
### Requirement: 补丁脚本只支持已验证版本和已准入项目

脚本 MUST 明确限制到已经验证的 awehitch 版本，MUST 列出本版本实际准入的补丁，MUST 逐项报告结论，且 MUST 幂等。文件缺失或锚点不能唯一命中时，脚本 MUST 不修改该项并以非零退出码结束。

#### Scenario: 版本不匹配

- **WHEN** 当前安装版本不是脚本声明的已验证版本
- **THEN** 脚本 MUST 拒绝修改安装包

#### Scenario: 重复运行

- **WHEN** 所有准入补丁均已存在时再次运行脚本
- **THEN** 脚本 MUST NOT 重写已处理的第三方包文件
### Requirement: 补丁前保留原件

系统 MUST 在首次改动每个第三方包文件前创建同目录 `.orig` 备份，已有备份 MUST NOT 被覆盖。

#### Scenario: 重复重放

- **WHEN** 同一补丁被多次检查或重放
- **THEN** 首次创建的 `.orig` 原件 MUST 保持不变
### Requirement: 0.3.2 的准入补丁

awehitch 0.3.2 只准入四项第三方包代码补丁：固定浏览器缩放、剔除长消息折叠标签、保持 Codex（代码代理）项目级注册、使发送文本满足 `[C2C]` 和 1024 字节限制。脚本 MAY 同时托管已经取得真实失败证据的授权按钮覆盖和安全观测。旧补丁 2、5、6 MUST NOT 重放，除非未来重新取得对应版本的真实失败证据。

#### Scenario: 发送折叠长消息

- **WHEN** 发送一条小于 1024 字节且页面会折叠的控制消息
- **THEN** 读回比对 MUST 忽略末尾的展开或收起标签并报告发送成功

#### Scenario: 运行接入命令

- **WHEN** 开发者执行 `awehitch up`
- **THEN** Codex（代码代理）用户级配置 MUST 逐字节不变
- **THEN** 只有包含正确工作区、`--harness codex`、控制面开关和三会话槽位的项目级配置 MUST 被诊断为已接入

#### Scenario: 渲染发送文本

- **WHEN** 按允许的最长连接器名渲染现有 Codex（代码代理）技能
- **THEN** 每个需要发送的控制文本块 MUST 以 `[C2C]` 开头且不超过 1024 字节
### Requirement: 只更新已验证客户端

模板补丁应用成功后，脚本 MUST 只重渲染本次验证范围内且已经存在的 Codex（代码代理）技能，MUST NOT 创建或改写未参与验证的其他客户端安装。

#### Scenario: 其他客户端未参与验证

- **WHEN** 模板补丁应用成功但其他客户端不在本轮验证范围内
- **THEN** 脚本 MUST NOT 创建或改写该客户端的技能文件
### Requirement: 固定项目配置支持三个工作区直接使用

每个受管仓库 MUST 通过自己的项目级 Codex（代码代理）配置固定工作区，并 SHALL 配置 `--harness codex`、`AWEHITCH_CONTROL_PLANE=1` 和 `AWEHITCH_MAX_PARALLEL_SESSIONS=3`。切换受管仓库 MUST NOT 依赖改写用户级活动工作区配置或重新执行 `up`。

#### Scenario: 在三个受管仓库间切换

- **WHEN** 全机服务已经健康，使用者分别从三个受管仓库启动 Codex（代码代理）会话
- **THEN** 每个会话 MUST 连接自己项目配置指定的工作区
- **THEN** 三个同时存活的会话 MUST 能分别取得 `codex`、`codex-s1` 和 `codex-s2` 浏览器配置档

#### Scenario: 项目配置不完整

- **WHEN** 项目配置的工作区、代理类型、控制面开关或三会话槽位任一项缺失或错误，或者仍使用不兼容的旧传输字段
- **THEN** `doctor`（诊断命令）MUST NOT 把该工作区报告为已正确接入
### Requirement: 稳态工作流只按需启动或修复

Codex（代码代理）技能的正常任务入口 MUST 先读取全机状态并运行无修复诊断。服务健康且当前项目配置有效时，流程 MUST NOT 运行 `up`；只有服务未运行、工作区未登记或诊断明确要求连接器修复时，流程 SHALL 执行相应的启动或修复动作。

#### Scenario: 全机服务和项目配置健康

- **WHEN** 使用者从已正确接入的仓库开始正常任务
- **THEN** 技能 MUST 复用现有服务和连接器，而不重新运行 `up`

#### Scenario: 重启后服务未运行

- **WHEN** 状态检查确认全机服务未运行
- **THEN** 技能 SHALL 运行一次 `up` 恢复服务，并在需要时按诊断结果修复连接器
### Requirement: 授权按钮覆盖可安全重放

补丁脚本 MUST 只拥有选择器覆盖中的 `connector.signInButton` 字段，并 MUST 保留所有其他未知字段。覆盖缺失时脚本 SHALL 创建或补齐受管字段；受管字段与预期一致时 MUST 保持文件不变；受管字段存在人工差异或配置不是有效 JSON（数据格式）时 MUST 停止而不覆盖。

#### Scenario: 覆盖文件包含其他字段

- **WHEN** 授权按钮字段缺失且覆盖文件还包含其他自定义字段
- **THEN** 脚本 SHALL 只补齐授权按钮字段并 MUST 保留其他字段

#### Scenario: 授权按钮字段已被人工修改

- **WHEN** 当前授权按钮候选与脚本管理值不同
- **THEN** 脚本 MUST 报告差异并以非零状态停止，且 MUST NOT 重写覆盖文件
### Requirement: 授权流程提供无敏感信息的阶段观测

授权自动流程 MUST 记录选择器加载、连接点击、登录按钮状态与点击、授权页出现和最终授权验证这些阶段，并 MUST NOT 记录配对码、令牌、页面正文、原始错误文本、选择器内容或带参数地址。连接点击后流程 SHALL 在最多 10 秒内每 500 毫秒重新解析一次登录按钮，按钮出现后立即继续。

#### Scenario: 登录按钮延迟出现

- **WHEN** 连接点击成功后登录按钮没有立即出现，但在 10 秒窗口内变为可见
- **THEN** 自动流程 MUST 重新解析并点击该按钮，而不是直接进入授权超时

#### Scenario: 授权失败需要排查

- **WHEN** 授权流程停在任一阶段
- **THEN** 日志 MUST 指出最后完成的安全阶段和结果类别
- **THEN** 日志 MUST NOT 暴露任何授权凭据或页面敏感内容
