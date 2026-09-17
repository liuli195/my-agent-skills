# ChatGPT 协作能力：调研结论与本机现状

> **给后续 Agent（代理）**：接手与 ChatGPT 协作、awehitch、或本机这套环境有关的任务前，
> **请先读完本文档**。里面有本机当前的完整状态、所有本地补丁与修复、以及已知限制。
>
> 最后更新：2026-09-18

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

## 5. 本机当前完整状态

### 5.1 已安装组件

| 组件 | 版本 | 说明 |
|---|---|---|
| `awehitch` | 0.2.1 | npm 全局安装 |
| `cloudflared` | 2026.9.1 | Cloudflare 隧道客户端，`C:\Program Files (x86)\cloudflared\` |
| Node.js | v24.18.0 | 引擎要求 ≥ 20 |

### 5.2 三个仓库的接入

**每个工作区在 ChatGPT 里各有一个专属连接器，同一账号下同时存在多个。**

| 仓库 | 连接器名 |
|---|---|
| `D:\My Project\my-agent-skills` | `awehitch · my-agent-skills` |
| `D:\My Project\Quant-Research-Lab` | `awehitch · Quant-Research-Lab` |
| `D:\My Project\Wow Addons` | `awehitch · Wow Addons` |

**两个客户端都做成了"按项目隔离"，在哪个仓库就用哪个仓库，不需要任何切换命令：**

| 客户端 | 接入方式 |
|---|---|
| **Claude Code** | 每个仓库一条 **local 范围**的 MCP 登记（存在 `~/.claude.json` 里、**按项目分桶**，项目目录里不留文件）。用 `claude mcp add-json ... -s local` 在各自仓库目录里执行 |
| **Codex** | 每个仓库一份 **`.codex/config.toml`**（项目级配置，优先级高于用户级）。`mcp_servers` 不在被禁止的项目配置项名单里，所以合法。**需要项目被标记为 trusted 才生效** |

技能文件（两份，均已渲染）：

- `~/.claude/skills/awehitch/SKILL.md`
- `~/.codex/skills/awehitch/SKILL.md`

### 5.3 三个补丁（改的是 awehitch 安装包，`npm update -g awehitch` 会全部冲掉）

> **重打用 `scripts/awehitch-local-patches.ps1`，不要手工改。**
> 它会**先自检每个缺陷现在还在不在**，只在"确认仍存在"时才动手：
> 判定为"上游已处理"或"判不准"一律**不打**，并列出来要求人工确认（退出码 1）。
> 幂等，可随时重跑。自检是**静态启发式**（读代码找特征），不是运行时验证。

#### 补丁 1：浏览器启动参数 — **不打则整条链路完全不可用**

- **文件**：`%APPDATA%\npm\node_modules\awehitch\dist\control-plane\browser.js`（备份 `.orig` 同目录）
- **改动**：启动参数数组加上 `--force-device-scale-factor=1`
- **原因**：不打这个补丁，本机 Chrome 报 `devicePixelRatio 0.909`、视口宽度是正常值的 1.1 倍，
  Playwright（浏览器自动化库）的**每一次点击都被判定为"被其他元素遮挡"**——
  ChatGPT 输入框和连接器表单全部点不动。**重建浏览器配置无效（已实测）。**
- **验证**：交替各跑两轮，带参数四次全成功、不带四次全失败，100% 复现
- **重打**：在 `launchOptions.args` 数组里加回该字符串（两处启动都会用到）

#### 补丁 2：技能模板 — 解决多工作区下连接器名写死

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

### 5.4 两个修复

#### 修复 3：选择器覆盖 — **在状态目录，升级不会冲掉**

- **文件**：`%LOCALAPPDATA%\awehitch\control-plane\selectors.json`
- **内容**：覆盖 `connector.signInButton`，用唯一命中的选择器
- **原因**：中文界面下，授权确认弹窗的按钮文字是「使用 awehitch · 某仓库 登录」。awehitch
  候选选择器里最后一条 `'登录'` 会**同时命中设置侧栏的「账户安全与登录」** → 匹配到 2 个 →
  **Playwright 严格模式拒绝点击 → 报错被 `.catch()` 静默吞掉 → 授权页永不出现**

#### 修复 4：被 awehitch 写坏的 Codex 配置 — **会复发**

- **文件**：`~/.codex/config.toml`（出问题时备份在 `config.toml.broken-<时间戳>`）
- **症状**：Codex 完全起不来，报 `failed to load bootstrap configuration` / TOML 解析错误
- **原因**：awehitch 写 TOML 时（`dist/adapters/codex.js` 的 `upsertCodexMcpEntry`），`body`
  结尾没有换行，与紧随其后的下一个表名**粘成一行**；并留下一个重复的
  `[sandbox_workspace_write]` 表
- **修法**：拆开粘住的那行，删掉重复的表块
- **注意**：**每次 `awehitch up` 都可能再次写坏**，升级或重连后如 Codex 起不来，先查这里

### 5.5 未跟踪文件（按仓库规则需走 PR）

- `.codex/config.toml`（本仓库的 Codex 项目级配置）
- `docs/research/playwright-c2c-implementation-plan.md`（归档的原始方案文档）
- `docs/research/chatgpt-collaboration-setup.md`（本文档）
- `scripts/awehitch-authorize.mjs`（授权补位脚本，见第 6 节第 1 条）
- `scripts/awehitch-local-patches.ps1`（本地改动自检与补齐，见第 5.3 / 8 节）

## 6. 已知限制

1. **授权步骤的自动化在本机不完全可靠**。修复 3 解决了"点击被静默吞掉"，但仍有残留问题
   未定位（复现 3 次）。**备用手段：本仓库的 `scripts/awehitch-authorize.mjs`** —— 它用已验证
   可用的固定序列完成同一件事（打开连接器 → 点「连接」→ 点「使用 … 登录」→ **现取**配对码 →
   提交）。Quant-Research-Lab 就是靠它接通的。仍不行时，改用技能里的 `manualFallback.steps`
   手动完成。
2. ~~**`awehitch_send_state` 常返回 `SEND_FAILED`**~~ —— **已由补丁 3 修复**。根因是长消息被
   折叠时「展开」按钮文字混进了读回比对，消息其实完整送达。若补丁丢失后重新出现该报错：
   **先看页面上那条消息是否完整**（完整就继续等回复，不要重发）。
3. **重启电脑后隧道地址会变**，需要重跑 `awehitch up -w <仓库>`；地址一变，ChatGPT 那边的
   连接器就需要重建。
4. **控制面浏览器是全机单例**（浏览器配置与锁都是全局一份），同一时刻只能服务一个工作区。
5. **`npm update -g awehitch` 会冲掉补丁 1 和补丁 2**（修复 3 不受影响）。
6. **Codex 的用户级配置里也有一条** awehitch 条目，指向最后一次 `up` 的仓库；在有
   `.codex/config.toml` 的仓库里它会被项目级覆盖。在没有项目级配置的新仓库里，它会指向
   那个过期的仓库——新增仓库时记得补一份项目级配置。

## 7. 给后续 Agent 的说明

- **不要另行发明流程**。`awehitch` 用户级技能（Skill）里有完整用法，按它执行。
- **多工作区时务必确认连接器名**：`awehitch doctor -w <workspace> --json` → 读 `connectorName`。
- **长消息可以直接发**（1 KB 以内）。若见到 `SEND_FAILED`／"fragmented send"，那是补丁 3 丢失的
  信号，**不是真的碎片化**——先确认页面上那条消息是否完整，完整就继续，不要重发。
- **控制面是全机单例**，别指望两个工作区同时用。
- **改任何东西前先读本文档第 5 节**，确认你要改的是不是已经有本地补丁/修复。
- **用户对"能力宣称"很敏感**：把结论按证据层级说清楚（已实测 / 已读源码 / 我的推断），
  不要把推断说成已具备的能力。

## 8. 出问题时怎么办

0. **先跑一次 `pwsh -File scripts/awehitch-local-patches.ps1`** —— 它会自检三处补丁与用户级
   配置条目，缺什么补什么；有需要人工判断的会明确列出来。**升级 awehitch 或跑过
   `awehitch up` 之后，这是第一步。**
1. `awehitch doctor -w <仓库> --json`（它会自动修复服务与隧道）
2. **Codex 起不来** → 查 `~/.codex/config.toml` 是不是又被写坏了（见修复 4）
3. **点击没反应 / 授权页不出现** → 确认补丁 1 与修复 3 还在
4. **技能里的连接器名不对** → 确认补丁 2 还在，必要时重新渲染技能
5. **授权步骤失败**（连接器已建好、只是没授权）→ 跑
   `node scripts/awehitch-authorize.mjs "<仓库绝对路径>" "<连接器名>"`
6. **确认是否已授权**：看 `%LOCALAPPDATA%\awehitch\auth\<workspaceId>.json` 里 `tokens` 的数量，
   大于 0 即已授权
7. 彻底重来：`awehitch stop -w <仓库>` 然后 `awehitch up -w <仓库>`

## 9. 来源

- 原始方案（归档）：[`playwright-c2c-implementation-plan.md`](./playwright-c2c-implementation-plan.md)
- [awehitch 仓库](https://github.com/wehuman01/awehitch) · [npm](https://www.npmjs.com/package/awehitch)
- [codex-with-chatgpt（上游）](https://github.com/XiaoDuoYa/codex-with-chatgpt)
- [Codex 配置基础（含项目级配置优先级）](https://learn.chatgpt.com/docs/config-file/config-basic.md)
- [Claude Code MCP 配置](https://code.claude.com/docs/en/mcp)
