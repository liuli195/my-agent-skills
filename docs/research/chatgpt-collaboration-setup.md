# ChatGPT 协作能力：调研结论与本机现状

> **给后续 Agent（代理）**：接手与 ChatGPT 协作、awehitch、或本机这套环境有关的任务前，
> **请先读完本文档**。里面有本机当前的完整状态、所有本地补丁与修复、以及已知限制。
>
> 最后更新：2026-09-21
>
> **当前结论**：本机已升级到 `awehitch 0.3.2`。升级后先在未打补丁版本上逐项实测，
> 保留补丁 1、3、4、7，并正式管理授权按钮覆盖与安全观测；旧补丁 2、5、6 不再重放。
> 后续升级也必须遵循“先升级、再实测、最后按失败证据适配补丁”，禁止整包重打旧补丁。

## 1. 这份文档的由来

用户提供了一份方案文档，要求据此调研、制定方案、落地实施并跑通链路。原始文档已归档为
[`playwright-c2c-implementation-plan.md`](./playwright-c2c-implementation-plan.md)，**原文未改动**。

**本文档记录的是调研之后的最终结论与实际落地状态——它与原始方案的路线不同。**

## 2. 原始方案主张什么

原始文档要解决的问题是：`codex-with-chatgpt` 这套「ChatGPT 当规划大脑、本地代理执行」的模式
**只支持 Codex**，别的代理用不了。它的主张是：

- **不 Fork** `codex-with-chatgpt`，MCP（模型上下文协议）/ Bridge（桥接）/ Workspace（工作区）后端原样复用
- 新写一个 `c2c-browser`（用 Playwright 统一控制 ChatGPT 网页），替换掉 Codex 专属的浏览器控制层
- 写一份所有代理共用的 `SKILL.md`，只依赖 Shell（命令行）与 CLI（命令行程序）

## 3. 调研结论：两个工具对比

调研中发现，文档设想的 `c2c-browser` **已经被别人做出来了**。

| | `codex-with-chatgpt`（原始方案的后端） | `awehitch` |
|---|---|---|
| 定位 | ChatGPT 只服务 Codex | ChatGPT 服务**任意**能调工具的代理 |
| 控制面 | **Codex 内置浏览器**（技能里写满 `agent.browsers.get("iab")`、`tab.markHandoff()`，只有 Codex 有） | **独立的本地 stdio MCP 服务器**，自带 Playwright 浏览器 |
| 数据面 | 9 个只读 MCP 工具 | **同一份**（工具名、参数、安全注解逐条一致，数据面改编自前者） |
| 隧道 / OAuth / 配对 | Cloudflare 隧道 + OAuth 2.1 | **同一套**（代码同源） |
| 敏感文件默认拒绝 | 33 条规则 | **33 条逐字相同** |
| 适配器 | 无（就是 Codex 专用） | codex / opencode / zcode 三个，契约仅 2 个方法 |
| 成熟度 | 5113 star，Codex 专属 | **2026-09-11 创建，很年轻** |

**关键判断**：原始方案想"自己写 Playwright 控制层"的那件事，`awehitch` 已经做完了——
那是整条链路**最脆弱**的部分（依赖 ChatGPT 网页的 DOM 结构），从零重做性价比低。

## 4. 最终采用的方案

**不重写浏览器控制层，改用 awehitch 作为引擎**，理由：

1. 控制面已被它做成了**独立的 stdio MCP 服务器**，任何能调 MCP 工具的代理都能用
2. 数据面与隧道/OAuth 那套直接复用，不必自己实现
3. 它的技能模板**不含任何 Codex 专属能力**，是真正通用的

代价（已知并接受）：

- 依赖一个很年轻的项目
- `awehitch` **没有 Claude Code 适配器**（只有 codex / opencode / zcode），Claude Code 侧要手工接

### 4.1 `0.3.2` 官方模型与本机固定配置（2026-09-21 重新通读）

> 本节先说明官方模型，再列出本机采用的固定配置差异。结论来自 `v0.3.2` 的 README、中文 README、
> `docs/CONTRIBUTING.md`、发布源码和本机 `awehitch 0.3.2 --help`。截至 2026-09-21，
> 官方 `main` 与 `v0.3.2` 都指向提交
> [`284939a`](https://github.com/Wehuman01/awehitch/commit/284939aff84f8439b2a2cd05e10cf3123fb027f6)，
> 因而当前 `main` 没有比发布版更新的正常使用流程。

#### 先分清三层状态

| 层 | 官方 `0.3.2` 的实际含义 | 生命周期 |
|---|---|---|
| Bridge（桥接服务）+ 隧道 + ChatGPT 连接器 | **全机一份**，服务工作区登记表中的所有目录；在另一个目录运行 `up` 是新增登记，不会替换 Bridge（桥接服务） | `stop` 只停服务；`off` 还会吊销全机令牌 |
| Codex（代码代理）用户级 MCP（模型上下文协议）配置 | `up` 把 `~/.codex/config.toml` 中唯一的 `awehitch` 条目更新为本次 `-w` 的目录，并写入 `--harness codex` | 决定**之后启动的** Codex 控制面进程绑定哪个工作区 |
| Codex 控制面进程与浏览器槽位 | 每个 Codex 会话启动自己的 stdio MCP（标准输入输出模型上下文协议）进程；首次用浏览器时，在全机 `codex` 槽位池里领一个槽 | 槽位跟随控制面进程，而不是跟随浏览器窗口 |

工作区登记的源码注释明确说：`0.2.6` 已把“最后一次 `up` 获胜”改为“一台机器一个
Bridge（桥接服务），`up -w` 只添加目录”；活着的 Bridge（桥接服务）还会立即接收新登记，
无需重启（[`workspace/registry.ts:6-10`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/workspace/registry.ts#L6-L10)、
[`process/daemon.ts:204-237`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/process/daemon.ts#L204-L237)）。
官方 README 的命令说明仍写着“换目录会替换上一个工作区”，但同一文件的安全说明又写“只新增
登记”；中文 README 和 CONTRIBUTING 也残留了旧说法。这里以 `0.3.2` 发布源码和 `status`
实际输出的 `Registered workspaces` 为准（[README 矛盾位置](https://github.com/Wehuman01/awehitch/blob/v0.3.2/README.md#L125-L130)、
[`status` 源码](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/cli/index.ts#L1256-L1347)）。

#### 第一次安装与登记

官方最省事的方案是在三个项目的共同父目录运行一次 `awehitch up`，让一个工作区边界覆盖
下面的项目；需要更严格边界时，才分别运行 `awehitch up -w <仓库>` 登记三个仓库
（[官方快速开始](https://github.com/Wehuman01/awehitch/blob/v0.3.2/README_cn.md#L36-L56)）。
本机选择后者时，正常步骤是：

1. 在每个需要暴露的仓库各运行一次 `awehitch up -w "<绝对路径>" --json`。`--json` 是给
   Agent（代理）调用的后台模式；人工想看持续日志时用前台 `up`，`Ctrl+C` 停止，或用 `-d`
   转后台（[`up --help` 对应源码](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/cli/index.ts#L449-L470)）。
2. `up` 保证全机 Bridge（桥接服务）和隧道可用，把目录加入登记表，并在确有需要时建立或
   修复 ChatGPT 连接器。地址没变且已有授权令牌时，它不会碰 ChatGPT 页面
   （[`cli/index.ts:511-558`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/cli/index.ts#L511-L558)）。
3. 官方 Codex 适配器随后渲染技能，并更新**用户级** `~/.codex/config.toml` 的唯一
   `[mcp_servers.awehitch]`，其中包含本次工作区和 `--harness codex`
   （[`adapters/codex.ts:18-40`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/adapters/codex.ts#L18-L40)、
   [`adapters/codex.ts:76-108`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/adapters/codex.ts#L76-L108)）。
4. 首次连接时，自动流程是“登录 → 开发者模式 → 删除同名旧连接器 → 创建 → 配对 → 以
   Bridge（桥接服务）的 `tokenCount` 增长验证成功”，不是只相信页面提示
   （[`CONTRIBUTING.md:154-174`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/docs/CONTRIBUTING.md#L154-L174)）。

#### 官方切换模型与本机最终模型

官方默认由每次 `up -w <目标仓库>` 改写用户级 Codex（代码代理）条目；已经启动的会话不会
热切换，之后启动的会话读取新工作区。这个模型适合“一个活动工作区”，但每次换仓库都必须先
运行 `up`，并继续暴露旧格式用户配置被写坏的风险。

本机最终采用三份固定项目配置：三个仓库各自在 `.codex/config.toml` 写死自己的
`--workspace`，同时加入 `--harness codex` 和三槽环境值。用户级配置不保存 awehitch 条目，
补丁 4 阻止 `up` 改写它。因此切换仓库时不需要先运行 `up`，旧仓库会话和新仓库会话可并存；
只有全机 Bridge（桥接服务）未启动、工作区未登记或诊断明确要求修复时才运行 `up`。

#### 并发槽位：如何设置、查看和释放

- 默认是**每个 harness（代理类型）2 个**，可由 `AWEHITCH_MAX_PARALLEL_SESSIONS` 调到
  `1..16`；这是进程启动时读取的环境变量，不是 `up` 参数
  （[`slot.ts:6-33`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/slot.ts#L6-L33)）。
- 本机固定使用 3 个槽位，直接在三份项目配置的 `env` 中写
  `AWEHITCH_MAX_PARALLEL_SESSIONS="3"`，不新增 Windows 用户环境状态，也无需每次告诉
  Agent（代理）槽位数。
  官方 `0.3.2` 没有 `up --slots`、`slots list` 或 `slots release` 命令，`status` 也只显示
  Bridge（桥接服务）和工作区登记表。
- 当前会话可从 `awehitch_chat_info` 得到自己的槽位号和 profile（浏览器配置档）；官方没有
  汇总全部槽位占用的用户命令（[`server.ts:390-398`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/server.ts#L390-L398)）。
- 槽位在**第一次浏览器使用**时领取，并在控制面进程整个生命周期内保留。浏览器空闲默认
  10 分钟关闭，只关闭标签页/Chromium（浏览器）和浏览器锁，下次调用会自动重开；它**不会**
  释放会话槽（[`browser.ts:248-310`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/browser.ts#L248-L310)、
  [`server.ts:95-135`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/server.ts#L95-L135)）。
- 正常释放方式是结束持有它的 Codex 会话，使控制面进程退出；显式 `dispose()` 也会释放，但
  没有对应的官方 CLI（命令行程序）。进程异常死亡后，下一位申请者会回收陈旧租约；不要在
  原进程还活着时手删 `.session.lock`（[`browser.ts:354-390`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/browser.ts#L354-L390)、
  [`slot.ts:97-175`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/slot.ts#L97-L175)）。
- `awehitch stop` 只停止全机 Bridge（桥接服务），`awehitch off` 还会吊销 ChatGPT 令牌；两者
  都不是单个 Codex 控制面槽位的释放命令
  （[`cli/index.ts:753-778`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/cli/index.ts#L753-L778)、
  [`cli/index.ts:1226-1254`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/cli/index.ts#L1226-L1254)）。

槽位数按**所有仍存活的同类会话总数**计算，不按当前工作区重新计数。例如旧仓库还有 1 个
Codex 会话时，池大小 3 只给新仓库留下 2 个空位；若想保留旧会话，同时在新仓库再开 3 个，
池大小至少要 4。

#### 连接器重建、授权与正确的故障恢复

- 正常 `up` 在地址不变且已有授权时不会重建连接器。临时隧道地址过期时，官方做法是删除
  旧连接器并用新地址创建，**不要点 Reconnect（重新连接）**；旧地址已经失效
  （[官方故障说明](https://github.com/Wehuman01/awehitch/blob/v0.3.2/README_cn.md#L158-L169)）。
- `connector-setup` 使用没有 harness（代理类型）的 `default` 浏览器 profile（配置档）；官方
  Codex 条目带 `--harness codex`，普通会话使用 `codex`、`codex-s1`……。因此按官方配置时，
  连接器重建与 Codex 会话不会争用同一浏览器 profile（配置档）
  （[`connector.ts:1164-1202`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/control-plane/connector.ts#L1164-L1202)、
  [`codex.ts:81-88`](https://github.com/Wehuman01/awehitch/blob/v0.3.2/src/adapters/codex.ts#L81-L88)）。
- 第一诊断入口是 `awehitch doctor -w "<仓库>" --no-fix`。确认需要修复后再运行普通
  `doctor` 或 `connector-setup`；DOM（页面结构）变化先用 `connector-setup --dry-run`。
  想完全绕过自动设置浏览器，可先执行 `awehitch prefs set --setup-mode manual`，之后命令只
  打印人工步骤（[官方 Troubleshooting（故障排查）](https://github.com/Wehuman01/awehitch/blob/v0.3.2/README.md#L137-L150)）。
- 配对码一次性且约 5 分钟过期，失效后运行 `awehitch pair` 取新码；401 且刷新失败则重新
  授权。Bridge（桥接服务）状态“不确定”时先等候重查，禁止再拉起第二个 Bridge。
- 仍彻底卡死时才用 `awehitch stop` 后再 `awehitch up -w "<仓库>" --json`。只有确实要全机
  断开并吊销令牌时才用 `awehitch off`。

#### 发布版、当前 `main` 与本机补丁必须分开看

| 项目 | 官方 `v0.3.2` / 当前 `main` | 本机当前状态 |
|---|---|---|
| Codex 配置 | `up` 更新用户级条目，写入 `--workspace` 和 `--harness codex` | 补丁 4 禁止用户级更新；三个项目级条目固定工作区并包含 `--harness codex` |
| 控制面槽位 | 默认每 harness（代理类型）2 个，环境变量可调到 16 | 三份项目配置固定 `AWEHITCH_MAX_PARALLEL_SESSIONS=3` |
| 浏览器点击 | 原版启动参数 | 本机补丁 1 增加 `--force-device-scale-factor=1` |
| 长消息读回 | 原版比较逻辑 | 本机补丁 3 剔除末尾“展开/收起”文字 |
| 技能引导 | 官方模板 | 本机补丁 7 缩短并补齐 `[C2C]` 头；安装技能还曾出现模板渲染不一致，必须由正式渲染器校验 |
| 授权按钮 | 官方选择器 | 补丁脚本只托管 `selectors.json` 的 `connector.signInButton` |

本机证据：官方备份
`C:\Users\liuli\AppData\Roaming\npm\node_modules\awehitch\dist\adapters\codex.js.orig:29,67`
会更新用户级条目并写 `--harness codex`；本机补丁把写入改为 `const next = previous`，由三份
项目配置承担工作区、harness（代理类型）和槽位。2026-09-21 的真实验收已确认三个会话分别
领取 `codex`、`codex-s1`、`codex-s2`，并在连接器重建后完成三个工作区的消息往返。

## 5. 本机当前完整状态

### 5.1 已安装组件

| 组件 | 版本 | 说明 |
|---|---|---|
| `awehitch` | 0.3.2 | npm 全局安装；应用补丁 1、3、4、7、授权按钮覆盖与安全观测 |
| `cloudflared` | 2026.9.1 | Cloudflare 隧道客户端，`C:\Program Files (x86)\cloudflared\` |
| Node.js | v24.18.0 | 引擎要求 ≥ 20 |

### 5.2 接入模型

`0.3.2` 改为全机一个 Bridge（桥接服务）和一个 `awehitch` 连接器，通过工具参数选择已登记的
Workspace（工作区）。当前实测已登记 `my-agent-skills`、`Quant-Research-Lab` 和 `Wow Addons`。
`~/.c2c.json` 提供全局 `readonly`（只读）权限，各仓库不再保留重复的 `.c2c.json`。

本机有意采用三份固定项目配置，不使用官方的用户级活动指针。每份配置固定自己的工作区，
包含 `--harness codex`、`AWEHITCH_CONTROL_PLANE=1` 和
`AWEHITCH_MAX_PARALLEL_SESSIONS=3`；补丁 4 阻止 `up` 改写用户配置，并按完整语义检查项目
配置。当前只验证并更新 `~/.codex/skills/awehitch/SKILL.md`；Claude Code（代码代理）等其他
客户端不在本轮安装和验证范围内。

### 5.3 `0.3.2` 正式维护的本地改动

> **重打用 `scripts/awehitch-local-patches.ps1`，不要手工改。**
> 该脚本只支持已经实测的 `0.3.2`，重放补丁 1、3、4、7，并管理授权按钮覆盖与安全观测。准入依据是干净
> 版本上的真实入口失败，不是静态源码猜测。未来升级时应先安装、实测，再修改脚本；不得先跑旧脚本。

`0.3.2` 实测结果：补丁 1、3、4、7 仍能稳定复现并已用同入口转绿；补丁 2 的前提已被
全机单连接器模型取代；补丁 5 的旧命令接缝已失效且陈旧记录未阻塞；补丁 6 的旧版重连改写
不适用于新模板。因此下文补丁 2、5、6 的说明只保留为 `0.2.1` 历史证据，禁止据此重放。

#### 补丁 1：浏览器启动参数 — **不打则整条链路完全不可用**

- **文件**：`%APPDATA%\npm\node_modules\awehitch\dist\control-plane\browser.js`（备份 `.orig` 同目录）
- **改动**：启动参数数组加上 `--force-device-scale-factor=1`
- **原因**：不打这个补丁，本机 Chrome 报 `devicePixelRatio 0.909`、视口宽度是正常值的 1.1 倍，
  Playwright（浏览器自动化库）的**每一次点击都被判定为"被其他元素遮挡"**——
  ChatGPT 输入框和连接器表单全部点不动。**重建浏览器配置无效（已实测）。**
- **验证**：交替各跑两轮，带参数四次全成功、不带四次全失败，100% 复现
- **重打**：在 `launchOptions.args` 数组里加回该字符串（两处启动都会用到）

#### 历史补丁 2（`0.3.2` 不重放）：技能模板的多工作区说明

- **文件**：`%APPDATA%\npm\node_modules\awehitch\skill\SKILL.md.template`（备份 `.orig` 同目录）
- **改动**：题记后插入一段说明——每个工作区各有专属连接器、务必只用本工作区的、
  先 `awehitch doctor -w <workspace> --json` 读 `connectorName` 再替换
- **原因**：模板只把连接器名写死渲染进去，多工作区时技能里的名字在别的仓库是错的
- **为什么改模板而不是改技能文件**：`dist/adapters/codex.js:21` 会**每次 `awehitch up`
  无条件重写** `~/.codex/skills/awehitch/SKILL.md`（直接 `writeFileSync`，没有"已存在则跳过"
  的判断）。改技能文件会被冲掉，改模板不会。
- **重打**：插入那段说明后，**需重新渲染两份技能**（把 `{{HARNESS}}` 与 `{{CONNECTOR_NAME}}`
  做全局替换；`{{TASK_ID}}` 按设计保留给 Agent 填）

#### 补丁 3：读回比对剔除「展开」按钮文字 — **不打则长消息必报错**

- **文件**：`%APPDATA%\npm\node_modules\awehitch\dist\control-plane\composer.js`（备份 `.orig` 同目录）
- **改动**：`normalizeForCompare()` 里，在折叠空白之前加一句
  `.replace(/\s*(展开|收起|Show more|Show less)\s*$/i, "")`
- **原因**：消息长到一定程度（取决于**渲染高度**，不是行数）时，ChatGPT 会**折叠显示**，
  页面上出现一个「展开」按钮。awehitch 读回用户消息用的是 `innerText`，**把按钮文字也读进来了**
  → 比对必然失败 → 抛 `SEND_FAILED`。**而消息其实一字不少、完整送达。**
- **实测数据**（本机）：

  | 消息 | 页面上收到 | 读回比对 | 含「展开」 |
  |---|---|---|---|
  | 3 行 / 25 字节 | 3 行 | ✅ | 否 |
  | 10 行 / 95 字节 | 10 行 | ✅ | 否 |
  | 16 行 / 155 字节 | 17 行 | ❌ | **是** |
  | 24 行 / 235 字节 | 25 行 | ❌ | **是** |

  「收到行数」多出来的那一行就是「展开」——**消息内容本身从未丢失**。
- **打补丁后**：30 行 / 695 字节的消息返回 `{"ok":true,"sent":true}` ✅
- **重打**：在 `normalizeForCompare` 的 `.replace(/[​‌‍﻿]/g, "")` 之后插入上面那行
- **注意**：awehitch 的报错文案是 "fragmented send"，**具有误导性——实际上并没有碎片化发送**。
  1 KB 的硬限制是真实的（`control-plane/server.js` 里 `byteLength > 1024` 时拒绝）

#### 补丁 4：固定项目配置并保护用户配置

- **文件**：`dist/adapters/codex.js` 与 `dist/cli/index.js`（备份 `.orig` 同目录）
- **改动（三处，四处锚点）**：
  1. `setupCodexAdapter` 里 `const next = upsertCodexMcpEntry(...)` 改成 `const next = previous`
     —— 后面那个 `if (next !== previous)` 就永远不落盘，**用户级条目干脆不写**
  2. `codexAdapterStatus()` 加参数 `workspace`，并接受**项目级** `<仓库>/.codex/config.toml`
  3. `dist/cli/index.js` 的 doctor 调用处改成 `impl.status(workspace)`（② 靠它拿项目路径）
- **采用原因**：三个固定仓库需要直接启动和并存，不希望每次切换先运行 `up`；同时继续规避
  官方写入器覆盖旧格式用户配置时的损坏问题。
- **最终语义**：项目配置必须同时满足正确的 `--workspace`、`--harness codex`、三槽环境值，
  并且不能使用旧的 `type="stdio"` 字段。状态检查不再只认表头。
- **边界**：没有项目级配置的新仓库不会自动获得 awehitch；新增长期仓库时必须显式加入一份
  固定配置。连接器重建继续用 `default` profile（配置档），Codex 会话使用 `codex` 槽位池。
- **验证（2026-09-18 实测）**：
  - `awehitch up` 前后，`~/.codex/config.toml` 的 sha256 **逐字节一致**（确认不再写入）
  - `awehitch doctor` 仍报 `adapters.codex.installed: true`（确认改认项目级配置生效）
  - 直接调用验证：有项目级配置 → `mcpRegistered: true`；无 → `false`；不传参 → `false`（不崩）
- **重打**：四处单行锚点，任一处未能唯一命中即判「判不准」、不动手

#### 历史补丁 5（`0.3.2` 不重放）：旧版运行记录判断

- **文件**：`dist/bridge/runtime.js` 的 `findBridgeObservation`
- **改动**：把「记录里的进程是否还在」提到**端口探测之前** —— 进程已死即判「已停止」
- **原因**：重启之后，旧运行记录里的端口往往已被**另一个工作区**占着（默认端口 48765 是
  **全机共享**的，被占时新实例会静默退到临时端口，而旧记录里存的正是那条被占着的）。
  于是它判 `workspace_mismatch`（状态不明）→ `ensureBridge` 抛错拒绝启动 →
  `up` / `connector-setup` 全被挡住。记录里的进程都不在了，那份记录就是废的
- **边界（明确不修）**：「进程号被系统回收」那一支。修它必须把「状态不明」降级，而端口
  探测只是一次 HTTP 试探，服务短暂卡顿会被误判成死亡，**有误杀活体服务的风险**
- **验证（2026-09-18 实测）**：`tests/test_awehitch_local_patches.py` 走命令行接缝
  （`awehitch status -w <仓库> --json`）。红灯 `assert None is False` → 绿灯
- **重打**：整函数锚点，未能唯一命中即判「判不准」

#### 历史补丁 6（`0.3.2` 不重放）：旧版重新连接流程

- **文件**：`skill/SKILL.md.template`（两处）
- **改动**：① 重连那一节整节替换为实测三步 ② 同一模板里另一处引用同套标志的地方
  （doctor 门禁）**同步改** ③ 登录表述更正为异常路径
- **原因**：两个标志**只在一次运行的窗口内有效**（该次运行找到新地址就立刻落盘，下次
  比较新旧相等 → 判无变化），而 bridge 状态为「状态不明」时**根本不会亮**；真实链路还
  漏了**唯一真正重建连接**的那一步（`connector-setup`）
- **验证**：断言**渲染后**的技能文本含三步、且不再引用那两个标志
- **重打**：两处锚点，各须唯一命中

#### 补丁 7：引导词与校验词压到能发出去 — **不打则新会话拿不到角色设定**

- **文件**：`skill/SKILL.md.template`（三处）
- **改动**：① 引导词删掉**不改变任何决策**的表述、加 `[C2C]` + `STATE: BOOT` 头
  （**1361 → 816 字节**，余量 208）② 两处工作区校验词加 `[C2C]` + `STATE: CONNECT_CHECK`
  ③ 重连那节的校验词原写作字面量 `<connectorName>`，改成渲染占位符
- **原因**：唯一能发任意文本的通道（`awehitch_send_state`）硬性要求
  **以 `[C2C]` 开头**且 **UTF-8 字节数 ≤ 1024**，改前两条都踩，**永远发不出去**
- **验证**：断言**渲染后**文本 —— 全部 5 个送出的文本块都以 `[C2C]` 开头，按**最坏长度**
  连接器名替换后不超 1024
- **重打**：三处锚点，各须唯一命中

> **补丁 2 的启发式修正（2026-09-18）**：补丁 2 原先还有一条「上游已处理」的猜测，拿
> `connectorName` 等词当特征。但**上游自己的文字里就有 `connectorName`**（manualFallback
> 那段），于是它对**未打补丁的原始模板**也命中 → 补丁 2 被判「上游已处理」而**永不重打**，
> `npm update` 之后那段说明会**永久丢失**。实测踩到后已删除该猜测：猜错的代价是静默丢
> 掉一个补丁，比重复插入一段说明糟得多。

### 5.4 两个修复

#### 修复 3：选择器覆盖 — **在状态目录，升级不会冲掉**

- **文件**：`%LOCALAPPDATA%\awehitch\control-plane\selectors.json`
- **内容**：覆盖 `connector.signInButton`，用唯一命中的选择器
- **原因**：中文界面下，授权确认弹窗的按钮文字是「使用 awehitch · 某仓库 登录」。awehitch
  候选选择器里最后一条 `'登录'` 会**同时命中设置侧栏的「账户安全与登录」** → 匹配到 2 个 →
  **Playwright 严格模式拒绝点击 → 报错被 `.catch()` 静默吞掉 → 授权页永不出现**
- **管理方式**：正式补丁脚本只拥有 `connector.signInButton`；缺失时合并、相同时跳过、已有
  不同值或 JSON（结构化配置）损坏时停止，绝不覆盖其他人工字段。
- **时序修复（2026-09-21 实测）**：第一次真实重建中，Connect（连接）点击成功，但固定等待
  1.2 秒后登录按钮仍为 0，随后授权页超时。改为最多 10 秒、每 500 毫秒重新解析后，按钮在
  511 毫秒被发现并点击，授权页出现、配对成功、Bridge（桥接服务）收到令牌。
- **观测日志**：`%LOCALAPPDATA%\awehitch\logs\connector-auth-observer.log` 只记录阶段、数量、
  可见性、耗时、结果和错误类型，不记录选择器文本、网址、配对码、令牌或原始错误消息。

#### 修复 4：awehitch 写坏 Codex 配置 — **由固定项目配置规避**

- **文件**：`~/.codex/config.toml`（出问题时备份在 `config.toml.broken-<时间戳>`）
- **症状**：Codex 完全起不来，报 `failed to load bootstrap configuration` / TOML 解析错误
- **根因（源码级，2026-09-18 确认）**：`setupCodexAdapter` 每次 `up` 都往用户级配置写 awehitch
  条目。它覆盖**旧格式**条目时（旧格式自带 `[mcp_servers.awehitch.env]` 子表）**同时踩两层**：
  1. `upsertCodexMcpEntry` 替换用的 `body` **结尾没有换行** → 与遗留的子表头**粘成一行**
  2. `findTableToml` 把**任何** `[xxx]` 表头都当块边界，认不出子表是自己的 → 子表被**遗留**
     下来，与新格式的内联表 `env = { ... }` 冲突（TOML 重复定义）

  实测（Python `tomllib`）：

  | 写法 | 结果 |
  |---|---|
  | 只拆开粘住的行（保留遗留子表） | ❌ `Cannot declare ('mcp_servers','awehitch','env') twice` |
  | 拆开粘行 **+ 删掉遗留子表** | ✅ 通过 |
  | 现状（粘行） | ❌ `Expected newline or end of document after a statement` |

  **所以光"拆开粘行"不够** —— 是两层叠加。**触发条件是"覆盖旧格式条目"**，干净的配置不会踩到。
- **现在的状态**：本机明确不使用官方用户级活动指针。补丁 4 禁止写入用户配置，三份项目
  配置直接提供正确工作区、`--harness codex` 和三槽环境值；因此既不触发旧格式覆盖，也不
  牺牲本机需要的槽位隔离。
- **存量处理**：补丁脚本不再删除用户配置。若旧条目已损坏，应优先从已核验备份恢复；
  确需人工修复时，必须同时处理粘行与遗留子表，并用 TOML（配置格式）解析器复核。
- **历史说明**：本条目原先标注「**会复发**」、修法是「手工拆行」—— 那是补丁 4 之前的状态。
  文档旧版还提到「重复的 `[sandbox_workspace_write]` 表」，2026-09-18 未复现（现只有一处、内容正常）

### 5.5 仓库内相关文件

- `.codex/config.toml`（本仓库的 Codex 项目级配置）
- `docs/research/playwright-c2c-implementation-plan.md`（归档的原始方案文档）
- `docs/research/chatgpt-collaboration-setup.md`（本文档）
- `scripts/awehitch-authorize.mjs`（授权补位脚本，见第 6 节第 1 条）
- `scripts/awehitch-local-patches.ps1`（本地改动自检与补齐，见第 5.3 / 8 节）

## 6. 已知限制

0. **跨控制进程读取新回复仍未通过实测。** `0.3.2` 能跨进程恢复同一个 `task_id` 对应的
   ChatGPT 对话，但发送进程退出后，用新控制进程读取该对话的新回复仍持续得到 `timeout`。
   这与 `replyAnchor`（回复锚点）仍由进程内状态承担相符。本轮不新增持久化状态基础设施：
   成本和回归风险高于当前收益，继续采用“同一次往返保持同一控制进程；超时保持非终态，
   不重建连接器、不新建对话、不重复发送”的调用侧规避，并将此项留给上游修复。

1. **授权步骤已补齐选择器和时序保护。** 自动流程现在会在 Connect（连接）后短时轮询登录
   按钮，并已通过隧道回收后的真实连接器重建。若未来页面再次变化，先查看安全观测日志；
   **备用手段**仍是 `scripts/awehitch-authorize.mjs` 或技能返回的 `manualFallback.steps`。
2. ~~**`awehitch_send_state` 常返回 `SEND_FAILED`**~~ —— **已由补丁 3 修复**。根因是长消息被
   折叠时「展开」按钮文字混进了读回比对，消息其实完整送达。若补丁丢失后重新出现该报错：
   **先看页面上那条消息是否完整**（完整就继续等回复，不要重发）。
3. **`0.3.2` 的重连异常分类尚未完成全部受控实测。** 当前应先运行 `doctor --no-fix`
   读取状态；远端错误、生成中和等待超时一律保留原任务与对话，不运行 `connector-setup`。
   只有诊断明确要求建立或修复连接器，且没有其他高级操作进行中时，才运行该命令并等待最终结果。
   `0.2.1` 的“移动每工作区运行记录”五步流程仅属历史证据，不得用于全机服务模型。
4. `0.3.2` 使用全机 Bridge（桥接服务）和连接器，并提供按 harness（代理类型）的会话槽。
   三份固定项目配置用 `--harness codex`，连接器重建使用 `default` profile（配置档），源码上
   两者不应竞争同一浏览器目录。2026-09-21 已用三个并存控制面会话确认 `codex`、`codex-s1`、
   `codex-s2`，并在它们存活时用 `default` 完成连接器重建；三个工作区随后分别完成消息往返。
5. **`npm update -g awehitch` 会冲掉第三方安装包内的本地补丁。** 不要立即重打；必须先在
   新版本上逐项实测，再只适配仍能复现且收益合理的项目。
6. **固定项目配置只覆盖三个长期仓库。** 新仓库不会自动获得 awehitch；需要长期使用时，复制
   已验证的项目配置并改成该仓库绝对路径，不能依赖 `up` 写用户级配置。
7. **官方没有槽位管理命令。** 浏览器空闲关闭不释放槽位；槽位随控制面进程退出而释放，
   死进程的陈旧租约由下一位申请者回收。`status` 不显示槽位池，`stop/off` 也不释放单个槽位。

## 7. 给后续 Agent 的说明

- **不要另行发明流程**。`awehitch` 用户级技能（Skill）里有完整用法，按它执行。
- **三个长期仓库直接使用各自固定配置**：平时先查 `awehitch status --json`，健康且已登记时
  不运行 `up`。只有服务停止、目标未登记或 `doctor --no-fix` 明确要求时才修复。
- **长消息可以直接发**（1 KB 以内）。若见到 `SEND_FAILED`／"fragmented send"，那是补丁 3 丢失的
  信号，**不是真的碎片化**——先确认页面上那条消息是否完整，完整就继续，不要重发。
- **高级操作继续串行执行**：一个操作未得到最终结果前，不启动另一个控制操作。
- **重连不要凭直觉**：按「已知限制 3」的 `0.3.2` 规则区分超时、远端错误和明确连接器损坏。
- **不要把槽位数塞进每次 `up` 的口令**：三份项目配置已经固定为 3；切换仓库也不需要运行
  `up`。
- **改任何东西前先读本文档第 5 节**，确认你要改的是不是已经有本地补丁/修复。
- **用户对"能力宣称"很敏感**：把结论按证据层级说清楚（已实测 / 已读源码 / 我的推断），
  不要把推断说成已具备的能力。

## 8. 出问题时怎么办

0. 普通故障可先运行 `pwsh -File scripts/awehitch-local-patches.ps1` 检查 `0.3.2` 的正式本地改动。
   **版本升级时不要先跑脚本**：先备份、安装干净版本并逐项实测，再按失败证据适配脚本。
1. `awehitch doctor -w <仓库> --json --no-fix`（只读取状态，先分类而不自动修复）
2. **连不上 / 刚重启过** → 见「已知限制 3」：先诊断，不把远端错误或超时当成连接器损坏。
3. **Codex 起不来** → 查 `~/.codex/config.toml`。补丁脚本不再自动清理用户配置；
   从升级前备份恢复，或在确认目标块后人工处理，不要让脚本猜测删除。
4. **点击没反应 / 授权页不出现** → 确认补丁 1 与修复 3 还在
5. **找不到工作区** → 先用 `awehitch status` 查看机器登记表，再用全机 `awehitch` 连接器
   调用 `list_workspaces`；未登记则运行 `awehitch up -w "<仓库>" --json`
6. **授权步骤失败**（连接器已建好、只是没授权）→ 跑
   `node scripts/awehitch-authorize.mjs "<仓库绝对路径>" "<连接器名>"`
7. **确认是否已授权**：看 `%LOCALAPPDATA%\awehitch\auth\<workspaceId>.json` 里 `tokens` 的数量，
   大于 0 即已授权
8. **槽位满** → 结束不再使用的 Codex 会话并确认其控制面进程退出；不要只关 Chrome，
   不要手删活进程的 `.session.lock`。官方 `0.3.2` 没有单槽位释放命令。
9. 不使用 `0.2.1` 的移动运行记录或强制停止流程；`0.3.2` 的恢复按诊断结果串行执行。

## 9. 来源

- 原始方案（归档）：[`playwright-c2c-implementation-plan.md`](./playwright-c2c-implementation-plan.md)
- [awehitch 仓库](https://github.com/wehuman01/awehitch) · [npm](https://www.npmjs.com/package/awehitch)
- [codex-with-chatgpt（上游）](https://github.com/XiaoDuoYa/codex-with-chatgpt)
- [Codex 配置基础（含项目级配置优先级）](https://learn.chatgpt.com/docs/config-file/config-basic.md)
- [Claude Code MCP 配置](https://code.claude.com/docs/en/mcp)
