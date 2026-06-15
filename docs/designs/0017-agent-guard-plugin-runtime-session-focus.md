# Agent Guard Plugin Runtime 与会话焦点技术实现方案

状态：草案

来源：

- GitHub Issue [#14](https://github.com/liuli195/my-agent-skills/issues/14)
- GitHub Issue [#17](https://github.com/liuli195/my-agent-skills/issues/17)
- GitHub Issue [#19](https://github.com/liuli195/my-agent-skills/issues/19)
- PRD：[Agent Guard Plugin Runtime 与会话焦点 PRD](../prd/0017-agent-guard-plugin-runtime-session-focus-prd.md)
- ADR：[0002 Agent Guard Plugin Runtime 与会话焦点](../adr/0002-agent-guard-plugin-runtime-session-focus.md)

更新时间：2026-06-15

## 目标

把 Agent Guard（代理守卫）升级为 Plugin-first（插件优先）架构。Plugin（插件）提供通用 Runtime code（运行时代码）、Hook Adapter（钩子适配器）、Hook Router（钩子路由器）和固定 lifecycle Hook（生命周期钩子）。

项目级和用户级只保留 Guard Profile（守卫画像）与运行态数据，不再复制 Runtime code（运行时代码）。

第一版只实现：

- `SessionStart` Hook（会话启动钩子）。
- `PreToolUse` Hook（工具使用前钩子）。
- Session Observation（会话观察记录）。
- Session Focus Binding（会话焦点绑定）。
- 显式 Guard Instance（守卫实例）激活、切换、关闭。
- 当前焦点实例上的权限判断和状态推进。

第一版不实现：

- Git Hook（Git 钩子）。
- Subject Resolver（主体解析器）。
- Hook Binding（钩子绑定）。
- 无 `session_id` 的 Hook（钩子）。
- Claude `PermissionRequest`。
- 旧运行态迁移或旧输出兼容。

## 总体流程

1. 用户安装 Agent Guard Plugin（插件）。
2. Plugin（插件）注册 `SessionStart` 和 `PreToolUse` lifecycle Hook（生命周期钩子）。
3. `SessionStart` 触发时，Runtime（运行时）记录 Session Observation（会话观察记录）。
4. 用户运行 `$agent-guard-run activate`。
5. Activation Service（激活服务）读取当前 Session Observation（会话观察记录）。
6. 用户选择 Guarded Target（被守卫目标）。
7. 用户选择已有 active Guard Instance（活跃守卫实例）或创建新实例。
8. Runtime（运行时）写 Session Focus Binding（会话焦点绑定）。
9. `PreToolUse` 触发时，Runtime Router（运行时路由器）通过 Session Focus Binding（会话焦点绑定）找到当前实例。
10. Runtime Router（运行时路由器）按当前实例状态和 Guard Profile（守卫画像）规则返回 allow（放行）、ask（询问）或 deny（拒绝）。
11. 主 agent（主代理）通过 `$agent-guard-run state-completed` 主动提交状态完成事件。
12. State Transition Service（状态推进服务）只推进当前 Session Focus Instance（会话焦点实例）。

## 模块一：Plugin Package（插件包）

### 责任

- 提供 Codex 和 Claude 可安装的 Plugin（插件）根目录。
- 发布 Runtime code（运行时代码）、Hook（钩子）配置、Skill（技能）入口和模板。
- 区分源码目录与最终安装目录。

### 源码结构

```text
plugins/
  agent-guard/
    .codex-plugin/plugin.json
    .claude-plugin/plugin.json
    hooks/hooks.json
    skills/agent-guard*/
    scripts/hook_router.py
    scripts/guard_runtime/
    assets/templates/
```

`plugins/` 是仓库级插件源码根目录，后续本仓库开发的其他 Plugin（插件）也放在这里。

`plugins/agent-guard/` 可以直接作为最终插件根目录，也可以由打包流程复制生成最终插件目录。

### 安装约束

- Codex 使用 `.codex-plugin/plugin.json`。
- Claude 使用 `.claude-plugin/plugin.json`。
- Codex 和 Claude 都使用插件内 `hooks/hooks.json` 作为 lifecycle Hook（生命周期钩子）入口。
- 目标项目不复制 `scripts/guard_runtime/`。
- 项目级初始化只写 Guard Profile（守卫画像）和运行态目录约定。

## 模块二：Plugin Installer（插件安装器）

### 责任

- 从仓库源码目录安装或更新 Agent Guard Plugin（代理守卫插件）。
- 分别支持 Codex 和 Claude 的本地插件安装。
- 提供 dry-run（试运行）、授权安装和安装验证。
- 区分 Plugin（插件）安装和 Guard Profile（守卫画像）生成。

### 官方依据

- Codex Plugin（Codex 插件）根目录必须包含 `.codex-plugin/plugin.json`；`skills/`、`hooks/`、`assets/` 等目录位于插件根目录。Codex 默认读取插件根目录下的 `hooks/hooks.json`，也支持在 manifest（清单）中显式指定 hooks。
- Codex 本地插件应通过 marketplace（市场）机制暴露；Codex 安装后从自己的插件 cache（缓存）加载已安装副本，而不是直接从源码目录运行。
- Codex 插件 Hook（钩子）需要用户 trust（信任）当前 hook definition（钩子定义）后才会运行；Hook 命令可以使用 `PLUGIN_ROOT` 和 `PLUGIN_DATA`。
- Claude Plugin（Claude 插件）是自包含目录，包含 `.claude-plugin/plugin.json`，并可在插件根目录提供 `skills/`、`hooks/hooks.json` 等组件。
- Claude 插件 Hook（钩子）命令应通过 `${CLAUDE_PLUGIN_ROOT}` 引用插件根目录内脚本，避免写死安装路径。

### 输入

- 插件源码目录：`plugins/agent-guard/`
- 安装目标：Codex、Claude 或二者
- 操作模式：dry-run（试运行）、install（安装）、verify（验证）

### 规则

- 默认只输出 dry-run（试运行）计划。
- 写入或链接用户级插件位置前必须获得明确授权。
- 安装器优先生成或更新本地 marketplace（市场）入口，让 Codex / Claude 按官方插件机制发现和安装插件；不得直接写 Codex 内部 cache（缓存）作为主路径。
- 安装器只处理 Plugin（插件）文件和本地 marketplace（市场）元数据，不生成 Guard Profile（守卫画像）。
- 安装器不写目标项目 Hook（钩子）。
- 安装器不写目标项目 Git 配置。
- 安装器不接收 `--profile`，不绑定 Guard Profile（守卫画像）。
- 重复安装应采用更新语义，不创建重复插件条目。

### 验证

安装验证必须检查：

- `.codex-plugin/plugin.json` 存在且可解析。
- `.claude-plugin/plugin.json` 存在且可解析。
- `hooks/hooks.json` 只声明 `SessionStart` 和 `PreToolUse`。
- Codex Hook（Codex 钩子）命令通过 `PLUGIN_ROOT` 指向插件内 `scripts/hook_router.py`。
- Claude Hook（Claude 钩子）命令通过 `${CLAUDE_PLUGIN_ROOT}` 指向插件内 `scripts/hook_router.py`。
- `scripts/guard_runtime/` 存在。
- `skills/` 入口存在。
- 本地 marketplace（市场）入口能指向 `plugins/agent-guard/`。
- 未写入 Git Hook（Git 钩子）或目标项目 `.codex/hooks.json`。

## 模块三：Hook Config（钩子配置）

### 责任

- 声明第一版固定 Hook（钩子）集合。
- 保证 Hook（钩子）入口不绑定 Guard Profile（守卫画像）。

### 固定集合

- `SessionStart`
- `PreToolUse`

### 禁止项

- Hook（钩子）命令不带 `--profile`。
- Hook（钩子）命令不读取 Hook Binding（钩子绑定）。
- Hook（钩子）命令不安装 Git Hook（Git 钩子）。
- Hook（钩子）命令不写业务规则。
- Hook（钩子）命令不选择 Guard Profile（守卫画像）。

### 不安装

- `UserPromptSubmit`
- `PostToolUse`
- `SubagentStart`
- `SubagentStop`
- Git `pre-commit`
- Git `pre-push`
- Claude `PermissionRequest`
- 任何无 `session_id` 的 Hook（钩子）

## 模块四：Hook Adapter（钩子适配器）

### 责任

- 把 Codex / Claude payload（载荷）转换成平台无关标准事件。
- 提取 `source + session_id + cwd`。
- 保留必要的工具调用信息给 Runtime Router（运行时路由器）。

### 标准事件

Hook Adapter（钩子适配器）只输出以下生命周期事件：

- `lifecycle.session_start`
- `lifecycle.pre_tool_use`

主 agent（主代理）主动提交事件：

- `state_completed`

标准事件最小 envelope（信封）：

```json
{
  "source": "codex",
  "event_type": "lifecycle.pre_tool_use",
  "context": {
    "session_id": "...",
    "cwd": "..."
  },
  "payload": {}
}
```

### 约束

- Hook（钩子）来源事件不得携带 `guard_profile_id` 或 `profile_id`。
- Hook Adapter（钩子适配器）不输出 `guard_profile_id`。
- Hook Adapter（钩子适配器）不读取 Hook Binding（钩子绑定）。
- 平台差异只放在 `source` 和 `metadata`。

## 模块五：Scope Resolver（作用域解析器）

### 责任

- 根据 Hook payload（钩子载荷）或运行命令的 cwd（工作目录）解析 project（项目级）或 user（用户级）作用域。
- 为 Session Observation（会话观察记录）和 Session Focus Binding（会话焦点绑定）提供 project-first（项目优先）查找顺序。

### 规则

- 能从 cwd（工作目录）解析到项目根时，优先使用 project（项目级）。
- 不能解析到项目根时，回退 user（用户级）。
- project-first（项目优先）只表示读取优先级，不表示 user（用户级）数据被删除或覆盖。

## 模块六：Session Observation Store（会话观察存储）

### 责任

- 记录当前会话事实。
- 为 `$agent-guard-run activate` 提供当前 `source + session_id + cwd`。
- 不表达当前焦点，不参与阻断判断。

### 写入规则

- `SessionStart` 触发时写入。
- 能解析到项目根时写 project（项目级）。
- 不能解析到项目根时写 user（用户级）。

建议路径：

- project（项目级）：`.local/guard/session-observations/<source>/<session_id>.json`
- user（用户级）：`%USERPROFILE%\.agents\guard\session-observations\<source>\<session_id>.json`

最小结构：

```json
{
  "source": "codex",
  "session_id": "...",
  "cwd": "...",
  "transcript_path": "...",
  "observed_at": "..."
}
```

### 读取规则

- activate（激活）按 project-first（项目优先）读取 observation（观察记录）。
- project（项目级）和 user（用户级）同时存在同一 `source + session_id` observation（观察记录）不算冲突。
- 找不到 observation（观察记录）时，activate（激活）中止，并提示确认 Plugin Hook（插件钩子）已启用、已信任且当前会话已经触发 `SessionStart`。

## 模块七：Session Focus Store（会话焦点存储）

### 责任

- 记录当前会话唯一焦点实例。
- 为 Runtime Router（运行时路由器）提供 `profile_id + instance_id`。

### 数据结构

```json
{
  "source": "codex",
  "session_id": "...",
  "scope": "project",
  "profile_id": "pr-flow",
  "instance_id": "agi_20260615_143012_a8f31c2d",
  "bound_at": "..."
}
```

`scope` 只允许：

- `project`
- `user`

建议路径：

- project（项目级）：`.local/guard/session-focus/<source>/<session_id>.json`
- user（用户级）：`%USERPROFILE%\.agents\guard\session-focus\<source>\<session_id>.json`

### 查找规则

- 0 个绑定记录：`allow + audit no_session_focus_instance`
- 1 个绑定记录：读取绑定指向的实例
- project（项目级）和 user（用户级）同时存在绑定记录：`deny + audit multiple_session_focus_bindings`
- 唯一绑定 JSON（JSON 数据）损坏：`deny + audit invalid_session_focus_binding`
- 唯一绑定缺必填字段：`deny + audit invalid_session_focus_binding`
- 绑定指向的实例不存在：`allow + audit no_session_focus_instance`
- 绑定指向的实例不是 active（活跃）：`allow + audit no_session_focus_instance`

### 切换规则

- 切换焦点采用同作用域替换语义。
- 切换 project（项目级）焦点时，不自动删除 user（用户级）绑定。
- 切换 user（用户级）焦点时，不自动删除 project（项目级）绑定。
- 切换成功写审计 `session_focus_changed`。

## 模块八：Instance Store（实例存储）

### 责任

- 创建、读取、列出和关闭 Guard Instance（守卫实例）。
- 使用 opaque `instance_id`（不透明实例 ID）。
- 不按 repo（仓库）、branch（分支）、PR 或 task id（任务 ID）推断实例。

### 数据结构

```json
{
  "instance_id": "agi_20260615_143012_a8f31c2d",
  "profile_id": "pr-flow",
  "status": "active",
  "title": "讨论 #17 Hook 插件化方案",
  "description": "基于 GitHub Issue #17，推进 Agent Guard Hook 和 Runtime 插件化重构设计。",
  "created_at": "...",
  "last_seen_at": "..."
}
```

状态只允许：

- `active`
- `closed`

建议路径：

- project（项目级）：`.local/guard/state/<profile_id>/<instance_id>/state.json`
- user（用户级）：`%USERPROFILE%\.agents\guard\state\<profile_id>\<instance_id>\state.json`

关闭实例只把状态改为 `closed`，不删除历史运行态。

## 模块九：Profile Store 与 Profile Validator（画像存储与校验器）

### 责任

- 读取 Guard Profile（守卫画像）。
- 校验新画像契约。
- 确保业务规则只存在于 Guard Profile（守卫画像）。

### Guard Profile 内容

Guard Profile（守卫画像）只保存业务语义：

- Guarded Target（被守卫目标）
- state machine（状态机）
- permissions（权限规则）
- guard checks（守卫检查）
- artifacts（产物）
- brief template（简报模板）
- runtime API version（运行时接口版本）

### 删除项

必须删除或停用：

- `subject-resolver.yaml`
- `hook-bindings.yaml`
- `subject_key_hash`
- `no_subject_match`
- `ambiguous_subject`
- `target_hint`

### Guarded Target

`target-model.yaml` 中的 `target` 是 Guarded Target（被守卫目标）。它应描述稳定对象，例如“PR 流程技能”，不应描述一次性上下文。

### Guard Point

- Guard Point（守卫点）不绑定 Hook（钩子）。
- Hook（钩子）只负责把平台事件交给 Runtime（运行时）。
- Runtime（运行时）找到当前 Session Focus Instance（会话焦点实例）后，按当前状态评估 permissions（权限规则）、artifacts（产物）和 guard checks（守卫检查）。

### 兼容性

- Guard Profile（守卫画像）必须声明 `runtime_api_version`。
- `runtime_api_version` 不兼容时，Runtime（运行时）返回 `allow + audit incompatible_runtime_api_version`，不能误阻断。

## 模块十：Activation Service（激活服务）

### 责任

- 提供 `$agent-guard-run activate`。
- 读取 Session Observation（会话观察记录）。
- 列出 Guarded Target（被守卫目标）。
- 列出 active Guard Instance（活跃守卫实例）。
- 创建新实例。
- 写 Session Focus Binding（会话焦点绑定）。
- 切换焦点。
- 关闭实例。

### 激活流程

1. 读取当前 Session Observation（会话观察记录）。
2. 找不到 observation（观察记录）时中止。
3. 列出 Guarded Target（被守卫目标）。
4. 用户选择 Guarded Target（被守卫目标）。
5. 列出该目标下 active Guard Instance（活跃守卫实例）。
6. 用户选择继续已有实例或创建新实例。
7. 新建实例时，主 agent（主代理）生成 `title` 和 `description` 草稿。
8. 用户确认后创建实例。
9. 写 Session Focus Binding（会话焦点绑定）。

### 表格模板

Guarded Target（被守卫目标）选择：

| 序号 | 作用域 | 守卫目标 | 类型 | 来源 | 边界 | 画像 ID |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | project | Hook 接入流程 | workflow | skills/agent-guard-hooks | 守卫 Hook 接入步骤 | agent-guard-hooks |
| 2 | user | PR 流程技能 | skill | skills/pr-flow | 守卫 PR 提交与合并顺序 | pr-flow |

实例选择：

| 序号 | 实例标题 | 实例说明 | 创建时间 | 最后使用 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 1 | 讨论 #17 Hook 插件化方案 | 基于 GitHub Issue #17，推进插件化重构设计。 | 2026-06-15 10:12 | 2026-06-15 11:03 | active |

固定新建选项：

| 选项 | 动作 |
| --- | --- |
| N | 创建新实例 |

新实例确认：

| 字段 | 内容 |
| --- | --- |
| 守卫目标 | PR 流程技能 |
| 实例标题 | 讨论 #17 Hook 插件化方案 |
| 实例说明 | 基于 GitHub Issue #17，推进 Agent Guard Hook 和 Runtime 插件化重构设计。 |
| 画像 ID | pr-flow |

## 模块十一：Runtime Router（运行时路由器）

### 责任

- 处理 `lifecycle.pre_tool_use`。
- 从 Session Focus Binding（会话焦点绑定）解析当前 `profile_id + instance_id`。
- 读取 Guard Profile（守卫画像）和 Guard Instance（守卫实例）。
- 按当前状态评估权限规则。
- 返回可映射到 Hook（钩子）阻断的结果。

### 输入约束

- Hook（钩子）来源的标准事件不得携带 `guard_profile_id` 或 `profile_id`。
- Router（路由器）不得根据 Hook（钩子）名称选择 Guard Point（守卫点）。
- Router（路由器）不得做 Subject（主体）推断。

### 事件规则

- `lifecycle.session_start` 只写 Session Observation（会话观察记录），不阻断、不推进状态。
- `lifecycle.pre_tool_use` 可以把 Runtime（运行时）返回映射为外部阻断。

## 模块十二：State Transition Service（状态推进服务）

### 责任

- 提供 `$agent-guard-run state-completed`。
- 只推进当前 Session Focus Instance（会话焦点实例）。
- 评估当前状态下的 Guard Point（守卫点）。
- 写状态推进审计。

### 规则

- 必须存在 Session Focus Instance（会话焦点实例）。
- 调用方不得指定 `profile_id` 或 `instance_id`。
- 无焦点实例时中止并提示先 activate（激活）。
- 多个绑定时中止并审计 `multiple_session_focus_bindings`。
- Hook（钩子）事件不得推进状态。
- 同一 `profile_id + instance_id` 的状态推进必须加锁。
- 状态推进时按当前状态评估 Guard Point（守卫点），不读取 Hook Binding（钩子绑定）。

## 模块十三：Guard Brief 与 Guard Injection（守卫简报与守卫注入）

### 责任

- 为当前 Session Focus Instance（会话焦点实例）生成 latest Guard Brief（最新守卫简报）。
- 在状态推进、权限拒绝、守卫点失败和状态变化后刷新简报。
- 在主 agent（主代理）推进 `state_completed` 前提供权威状态读取面。
- 使用 `brief_hash` 对同一 `source + session_id + profile_id + instance_id` 去重注入。

### 路径

- latest JSON（最新 JSON）：`.local/guard/latest/<profile_id>/<instance_id>/brief.json`
- latest Markdown（最新 Markdown）：`.local/guard/latest/<profile_id>/<instance_id>/brief.md`
- 注入记录：`.local/guard/injections/<source>/<session_id-hash>/<profile_id>/<instance_id>.json`

### 规则

- Guard Brief（守卫简报）必须保留；删除的是基于 `subject_key_hash` 的旧路径，不是删除简报机制。
- 简报必须通过 Session Focus Binding（会话焦点绑定）解析当前 `profile_id + instance_id`。
- 简报内容至少包含当前状态、允许下一步、禁止下一步、缺失产物、最近拒绝原因、权限摘要、完成条件、状态推进提示和审计位置。
- 终止状态不得提示继续推进，只提示流程已完成和审计位置。
- 注入内容只能来自 Runtime（运行时）生成的 latest Guard Brief（最新守卫简报）。
- 相同 `brief_hash` 在同一 `source + session_id + profile_id + instance_id` 内不得重复注入。
- `state_completed` 前 Runtime（运行时）必须确认当前 `brief_hash` 已经通过 brief（简报）入口读取并记录；未读取时返回 `brief_required`，不得推进状态。

## 模块十四：Audit Log 与 Lock Manager（审计与锁）

### Audit Log

审计事件至少覆盖：

- `session_focus_changed`
- `no_session_focus_instance`
- `invalid_session_focus_binding`
- `multiple_session_focus_bindings`
- `incompatible_runtime_api_version`
- `session_observation_missing`
- `state_completed`

### Lock Manager

- 锁粒度为 `profile_id + instance_id`。
- 状态推进必须持有锁。
- 锁超时必须审计并中止状态推进。

## 旧契约删除

本次不提供旧契约迁移或兼容层。需要直接删除或重写的旧契约：

- Subject Resolver（主体解析器）相关文件、模板、校验和测试。
- Hook Binding（钩子绑定）作为画像字段。
- Git Hook（Git 钩子）写入逻辑。
- 目标项目内复制 Runtime code（运行时代码）的初始化和升级逻辑。
- Guard Brief（守卫简报）、confirmations（确认记录）、overrides（覆盖记录）、latest brief（最新简报）中基于 `subject_key_hash` 的旧路径；Guard Brief（守卫简报）机制本身必须迁移到 `instance_id`，不得删除。
- 旧运行态兼容读取。
- 旧脚本输出兼容。

新实现不输出：

- `subject_key_hash`
- `no_subject_match`
- `ambiguous_subject`

## 测试计划

测试只验证外部行为，不测试内部函数实现细节。

必须覆盖：

- Plugin Package（插件包）：Codex / Claude 插件清单存在，`hooks/hooks.json` 只声明 `SessionStart` 和 `PreToolUse`。
- Plugin Installer（插件安装器）：dry-run（试运行）、授权安装、重复安装更新、安装验证、不写目标项目 Hook（钩子）或 Git 配置。
- Hook Adapter（钩子适配器）：Codex `SessionStart`、Codex `PreToolUse`、Claude `SessionStart`、Claude `PreToolUse` 转标准事件。
- Hook Adapter（钩子适配器）：缺失 `session_id` 的 lifecycle event（生命周期事件）返回错误或忽略，不进入焦点判断。
- Session Observation Store（会话观察存储）：project-first（项目优先）写入、读取和无 observation（观察记录）中止。
- Session Focus Store（会话焦点存储）：无绑定、单绑定、多绑定、坏 JSON（JSON 数据）、缺字段、实例不存在、实例 closed（关闭）。
- Instance Store（实例存储）：创建、列 active（活跃）、关闭、closed（关闭）不参与 Hook（钩子）判断。
- Activation Service（激活服务）：表格输出、选择已有实例、创建新实例、切换焦点绑定。
- Runtime Router（运行时路由器）：无焦点放行、绑定损坏拒绝、多绑定拒绝、有效焦点按状态判断。
- State Transition Service（状态推进服务）：无焦点中止、禁止指定 `profile_id` 或 `instance_id`、有效焦点推进、并发锁。
- Guard Brief（守卫简报）：激活生成 latest brief（最新简报）、状态推进刷新简报、同一 session（会话）按 `brief_hash` 去重注入。
- Guard Brief（守卫简报）：未读取当前 `brief_hash` 时，`state_completed` 返回 `brief_required` 且不推进状态。
- Profile Validator（画像校验器）：不再要求 `subject-resolver.yaml` 和 `hook-bindings.yaml`。
- 安装流程：不写 Git Hook（Git 钩子），不复制 Runtime code（运行时代码）到目标项目。

## 实施顺序

1. 建立 `plugins/agent-guard/` 源码目录和插件清单。
2. 新建 `hooks/hooks.json`，只注册 `SessionStart` 和 `PreToolUse`。
3. 实现 Plugin Installer（插件安装器）。
4. 实现 Hook Adapter（钩子适配器）和 Hook Router（钩子路由器）。
5. 实现 Scope Resolver（作用域解析器）。
6. 实现 Session Observation Store（会话观察存储）。
7. 实现 Session Focus Store（会话焦点存储）。
8. 实现 Instance Store（实例存储）。
9. 实现 Profile Store 与 Profile Validator（画像存储与校验器）。
10. 实现 Activation Service（激活服务）。
11. 实现 Runtime Router（运行时路由器）。
12. 实现 State Transition Service（状态推进服务）。
13. 实现 Guard Brief 与 Guard Injection（守卫简报与守卫注入）。
14. 实现 Audit Log 与 Lock Manager（审计与锁）。
15. 删除或重写旧契约相关模板、脚本和测试。
16. 跑完整测试并清理旧术语残留。
