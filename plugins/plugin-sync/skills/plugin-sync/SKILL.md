---
name: plugin-sync
description: Synchronize local agent Plugin（插件） state for Codex（代码代理） and Claude（代码代理）. Delegate MySpec（自有规格） and Build and Verify（构建与验证） lifecycle（生命周期） requests to their CLI（命令行程序）. Use when the user asks to check, refresh, update, install, enable, or sync local Plugin（插件）, marketplace（插件市场）, cache（缓存）, MySpec（自有规格）, or Build and Verify（构建与验证） state.
---

# Plugin Sync（插件同步）

## Use When（使用场景）

Use this Skill（技能） for local consumption-side Plugin（插件） state, not for release（发布） work.

Typical requests:

- Check whether Codex（代码代理） and Claude（代码代理） see the same Plugin（插件） versions.
- Refresh marketplace snapshot（市场快照） and update installed Plugin（已安装插件） versions.
- Diagnose stale cache（过期缓存）, missing subscription（缺少订阅）, disabled Plugin（未启用插件）, or restart（重启） needs.
- Diagnose or update MySpec（自有规格） or Build and Verify（构建与验证） through their CLI（命令行程序）.

## Safety Contract（安全边界）

- Default to read-only check（只读检查）.
- Do not update, install, enable, remove, or delete anything without explicit user authorization.
- Never run uninstall/remove（卸载/移除） unless the user names the exact Plugin（插件） and asks for it.
- Do not publish release（发布）, create tag（标签）, push（推送）, or modify release-flow（发布流程）.
- Do not scan the whole disk. For repository runtime（仓库运行时） work, use only the current repository, user-provided paths, or a user-confirmed bounded root.
- Claude（代码代理） Plugin（插件） updates for the same marketplace（插件市场） must run sequentially, not in parallel.

## MySpec（自有规格）委托边界

MySpec（自有规格）的安装、模式、诊断和更新默认不使用本 Skill（技能）的通用市场流程。CLI（命令行程序）拥有其路径、市场、模式和版本规则；除下述一次性显式例外外，Plugin Sync（插件同步）只按用户请求委托以下命令，不自行推断或复制规则：

- 诊断全部已支持 Agent（代理）：`myspec doctor --all`
- 诊断单个 Agent（代理）：`myspec doctor --pi`、`myspec doctor --claude` 或 `myspec doctor --codex`
- 初始化单个 Agent（代理）：`myspec init --pi`、`myspec init --claude` 或 `myspec init --codex`
- 初始化全部已安装 Agent（代理）：`myspec init --all`
- 切换开发模式：`myspec init --dev`
- 切换发布模式：`myspec init --release`
- 在发布模式统一更新：`myspec update`

修改性命令仍需用户显式授权。命令完成后只根据 CLI（命令行程序）的输出报告结果，不再检查或修正 MySpec（自有规格）的市场、安装目录、模式状态或版本。

一次性显式例外只在用户于当前对话中明确要求绕过 MySpec CLI（命令行程序），并点名客户端、MySpec 插件或来源及具体修改动作时成立。执行时：

- 只处理用户点名的精确对象和动作，不扩展到市场、其他插件、模式切换、更新或发布；
- 优先使用客户端原生安装管理命令；只有客户端没有精确操作入口时才允许定向编辑配置；
- 操作前保存目标状态和待修改文件，操作后运行 `myspec doctor --all`；失败或结果超出授权范围时只恢复本次保存的内容；
- “继续”“清理一下”或历史授权不构成例外，每次绕过都必须重新明确授权。

## Build and Verify（构建与验证）委托边界

Build and Verify（构建与验证）同样由 CLI（命令行程序）拥有其 Agent（代理）资源、模式和版本规则。只按用户请求委托：`build-and-verify doctor`、`build-and-verify init` 或 `build-and-verify update`，并且修改性命令仍需用户显式授权。不得检查、刷新、删除、提交或报告任何仓库 `.build-and-verify/runtime/` 快照。

## Client Target（客户端目标）

按以下顺序定位要操作的客户端及其关联插件状态：

1. 用户指定路径：直接使用。
2. 用户未指定：从 Windows（视窗系统）系统环境变量 `PATH`（可执行文件搜索路径）解析客户端，并使用客户端确认关联插件目录。
3. 无法获得可用关联状态时，回退客户端默认目录：
   - Codex（代码代理）：`~/.codex`
   - Claude（代码代理）：`~/.claude`
4. 默认目录也不存在时，使用当前进程／会话路径作为最后回退。

检查、刷新、更新和复查复用同一目标。客户端状态查询的输出是插件状态证据。

## Workflow（工作流）

1. If the request concerns MySpec（自有规格）, use the delegation commands above unless the current request satisfies the one-time explicit exception; for an exception, perform only its bounded native/manual action and verification.
2. If the request only contains MySpec（自有规格） or Build and Verify（构建与验证）, delegate its requested CLI（命令行程序） command and stop this workflow.
3. If the request has remaining non-MySpec（自有规格） scope, continue below only for that remaining scope.
4. Read `references/check.md` to resolve the Client Target（客户端目标） and run the read-only check（只读检查） flow for other plugins.
5. Classify findings using `references/status-taxonomy.md`.
6. If the user explicitly authorizes Codex（代码代理） updates, read `references/update-codex.md`.
7. If the user explicitly authorizes Claude（代码代理） updates, read `references/update-claude.md`.
8. Re-run the relevant read-only check（只读检查） after any authorized update.

## Defaults（默认值）

- marketplace（插件市场）: `my-agent-skills-marketplace` unless the user names another one.
- Plugin（插件） scope: plugins from the selected marketplace（插件市场） unless the user names specific plugins; MySpec（自有规格）默认只走委托边界，一次性显式例外按该区块收窄执行。

## Output（输出）

Keep output concise. Report:

- current status（当前状态）
- exact evidence（证据）
- action taken（已执行动作）, if any
- remaining next step（下一步）, if any

Do not present local Plugin（插件） update status as release（发布） completion status.
