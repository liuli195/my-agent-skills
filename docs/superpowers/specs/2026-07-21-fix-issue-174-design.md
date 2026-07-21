---
comet_change: fix-issue-174
role: technical-design
canonical_spec: openspec
archived-with: 2026-07-21-fix-issue-174
status: final
---

# Issue 174 Pi 兼容性设计

## 1. 目标与边界

本设计实现两个彼此独立、但共同面向 Pi（编码助手）宿主的最小适配：

1. Agent Guard（代理守卫）在 Pi（编码助手）自动捕获会话与全部工具调用，并把既有 Runtime（运行时）结果映射为继续或阻断。
2. PR Flow（拉取请求流程）在 Pi（编码助手）从安装包自身运行脚本，并输出不依赖源码仓库布局的恢复命令。

不修改 Guard Profile（守卫画像）格式、Session Focus（会话焦点）状态机、权限规则、审计契约、PR Flow（拉取请求流程）业务规则或目标仓库配置。不导入、配置、调用或修改其他 Pi（编码助手）插件。Codex（编码助手）和 Claude（克劳德）现有插件清单、Hook（钩子）和执行路径保持不变。

## 2. Agent Guard Pi 适配

### 2.1 结构

新增 `plugins/agent-guard/extensions/pi-agent-guard.ts`。Pi（编码助手）以包约定发现该 extension（扩展）；Codex（编码助手）和 Claude（克劳德）manifest（清单）未声明 `extensions/`（扩展目录），因此不会加载它。

extension（扩展）以 `import.meta.url`（模块位置）计算插件根目录，并定位同包 `scripts/hook_router.py`（钩子路由器）。它不导入 Python（派森）Runtime（运行时）内部模块，也不读取用户目录、缓存目录或其他插件状态。

```
Pi session_start                 Pi tool_call
       |                               |
       v                               v
Pi extension ----------------> stdin JSON + --source pi
                                       |
                                       v
                              hook_router.py
                                       |
                                       v
                    existing Guard Runtime / Profile / Audit
                                       |
                   allow --------------+-------------- deny or ask
                     |                                 |
                     v                                 v
                execute tool                    block current tool
```

### 2.2 会话启动

`session_start`（会话启动）处理器取得 Pi（编码助手）当前 session id（会话标识）、CWD（当前工作目录）和可用会话文件信息，向 Router（路由器）发送：

```json
{
  "session_id": "<pi-session-id>",
  "cwd": "<project-cwd>"
}
```

Router（路由器）以 `--source pi --event SessionStart`（来源和事件）运行，沿用既有 observation（会话观察记录）写入路径和数据格式。扩展同时仅在当前 Pi（编码助手）进程设置 `AGENT_GUARD_SOURCE=pi` 和 `AGENT_GUARD_SESSION_ID`，让既有技能辅助脚本默认使用同一会话；该环境状态不写入磁盘，也不改变 Runtime API（运行时接口）。会话启动失败只记录可诊断错误；真正的执行安全边界在后续每个工具调用。

### 2.3 工具调用

`tool_call`（工具调用）处理器覆盖 Pi（编码助手）的全部工具。它把 Pi（编码助手）的 `toolName`（工具名称）和完整 `input`（输入）直接映射为：

```json
{
  "session_id": "<pi-session-id>",
  "cwd": "<project-cwd>",
  "tool_name": "<tool-name>",
  "tool_input": { "...": "original input" }
}
```

Router（路由器）以 `--source pi --event PreToolUse`（来源和事件）处理该 JSON（数据）。扩展只解释既有 Router（路由器）的结果：

| Router（路由器）结果 | Pi（编码助手）结果 |
|---|---|
| `allow`（允许） | 返回，不阻断工具 |
| `deny`（拒绝）或 `ask`（询问） | 返回 `{ block: true, reason }`（阻断及原因） |
| 非零退出、无效 JSON（数据）或未知状态 | 返回 `{ block: true, reason }`（阻断及诊断原因） |

每个工具调用仅启动一次 Router（路由器）子进程。选择逐调用进程而不是常驻服务：现有 Router（路由器）已经是稳定 CLI（命令行）边界，逐调用不会引入连接、并发、状态同步或清理机制。延迟增加是可接受的安全换取。

### 2.4 最小共享变更

现有 Router（路由器）、运行时 CLI（命令行）和 Agent Guard（代理守卫）技能包装器将 source（来源）白名单从 `codex|claude` 扩展为 `codex|claude|pi`。非 Pi（编码助手）环境默认来源仍为 `codex`；仅 Pi extension（扩展）设置的当前进程环境会让辅助脚本默认选择 `pi`，避免会话焦点命名空间错配。

不得修改：

- `hooks/hooks.json`（钩子配置）；它仍是 Codex（编码助手）/Claude（克劳德）专用声明。
- Codex（编码助手）和 Claude（克劳德）manifest（清单）。
- Guard Runtime（守卫运行时）的 Guard Profile（守卫画像）评估、Session Focus（会话焦点）状态、审计或证据逻辑。
- Agent Guard（代理守卫）安装器；Pi（编码助手）按包约定发现资源，不引入第三套市场安装目标。

## 3. PR Flow Pi 执行入口

### 3.1 结构与调用

新增 `plugins/pr-flow/extensions/pi-pr-flow.ts`。该 extension（扩展）注册窄接口 `pr_flow`（PR Flow 工具），输入为受限的 PR Flow（拉取请求流程）命令与参数。它从 `import.meta.url`（模块位置）解析：

```text
../skills/pr-flow/scripts/pr_flow.py
```

再使用当前 Pi（编码助手）项目 CWD（当前工作目录）执行脚本。脚本位置永远来自包自身，项目位置继续由 `--project .`（项目参数）表达。

共享 PR Flow Skill（拉取请求流程技能）增加宿主路由：Pi（编码助手）存在 `pr_flow`（PR Flow 工具）时调用该工具；其他宿主保留当前已安装脚本运行方式。源码仓库维护者示例保留原始源码路径。

### 3.2 恢复命令

`pr_flow.py`（PR Flow 脚本）新增一个内部命令构造辅助函数，使用 `Path(__file__).resolve()`（当前脚本绝对路径）和 `sys.executable`（当前 Python 解释器）构造所有脚本型 `nextCommand`（下一命令）。

引用规则使用 Python（派森）标准库：Windows（视窗）使用 `subprocess.list2cmdline`（命令行引用），其他平台使用 `shlex.join`（Shell 引用）。现有 `gh`（GitHub 命令行）和 `git`（版本控制命令）恢复命令不改变。

## 4. 失败处理与安全性

- Router（路由器）调用失败时，Agent Guard（代理守卫）适配对当前工具调用 fail closed（失败即阻断），避免运行时缺失变成守卫绕过。
- PR Flow（拉取请求流程）工具向调用方返回脚本的结构化输出和退出状态，不吞掉失败，也不把插件 CWD（当前工作目录）误作目标仓库。
- 两个 extension（扩展）仅使用自身包内的相对资源解析；不接受外部脚本路径或任意可执行文件路径。

## 5. 测试策略

### 5.1 Agent Guard

- Router（路由器）接受 `source=pi`，并保持 Codex（编码助手）专属 deny（拒绝）输出与 Claude（克劳德）退出码语义不变。
- Pi（编码助手）extension（扩展）把会话启动、全部工具调用的输入映射到预期 Router（路由器）事件；验证 allow（允许）、deny（拒绝）、ask（询问）和 Router（路由器）失败。
- 验证 Pi（编码助手）的 session id（会话标识）在 `source=pi` 命名空间中与 Codex（编码助手）/Claude（克劳德）隔离。
- 以 Pi（编码助手）用户入口在初始化 Guard Profile（守卫画像）的测试项目中触发一次允许调用和一次拒绝调用。

### 5.2 PR Flow

- Pi（编码助手）工具从安装包自身定位 `pr_flow.py`（PR Flow 脚本），并在无 `plugins/pr-flow`（源码路径）的临时目标仓库以 `--project .`（项目参数）工作。
- 每种生成脚本恢复命令都包含脚本自身绝对路径；Windows（视窗）和非 Windows（视窗）引用均可执行。
- Codex（编码助手）与 Claude（克劳德）manifest（清单）、Hook（钩子）和源码仓库技能示例保持当前契约。
- 在两个目标仓库中从 Pi（编码助手）PR Flow Skill（拉取请求流程技能）入口执行诊断和至少一个可恢复停止状态。

## 6. 实施顺序

1. 先为 Agent Guard（代理守卫）添加 Pi（编码助手）extension（扩展）和 `source=pi` 兼容，并完成映射测试。
2. 再为 PR Flow（拉取请求流程）添加 Pi（编码助手）工具、宿主路由和自定位恢复命令。
3. 最后执行两个目标仓库的 Pi（编码助手）入口回归和完整仓库验证。
