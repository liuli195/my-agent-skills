# Playwright + codex-with-chatgpt 通用 Agent 改造方案

## 1. 背景与问题

`codex-with-chatgpt` 原生用于让 Codex 与 ChatGPT Web 协作。

原生架构：

```text
Codex
  │
  │ Browser / Computer Control
  ▼
ChatGPT Web
  │
  │ MCP
  ▼
C2C Bridge
  │
  ▼
Local Workspace
```

它实际分成两条链路：

- **Control Plane（控制通道）**：Codex 通过浏览器操作 ChatGPT Web，发送 INIT、PLAN、EXECUTED、REVIEW、DONE 等控制消息。
- **Data Plane（数据通道）**：ChatGPT Web 通过 MCP 读取本地 Workspace，包括文件、代码搜索、`git diff`、测试结果等。

当前问题：

- MCP / Bridge / Workspace 本身与 Codex Agent 没有强绑定，可以继续复用。
- 原生 Control Plane 与 Codex 的 Skill 和浏览器控制方式绑定。
- Claude Code、Pi、OpenCode 等 Agent 不能直接复用 Codex 专属浏览器控制逻辑。
- 如果为每个 Agent 单独实现一套浏览器控制，会产生重复开发和维护成本。

因此目标是：

> 用一个通用 Playwright 控制层替代 Codex 专属浏览器控制层，并提供一份所有 Agent 都可复用的统一 Skill。

---

## 2. 解决方案概述

新增两个独立组件：

```text
1. c2c-browser
2. 通用 C2C Skill
```

其中：

- `c2c-browser`：使用 Playwright 统一控制 ChatGPT Web。
- 通用 C2C Skill：定义所有 Agent 共用的协作流程，只依赖 Shell 和 CLI。

最终架构：

```text
Codex / Claude Code / Pi / OpenCode
                │
                │ 通用 Skill
                ▼
             Shell / CLI
                │
        ┌───────┴────────┐
        ▼                ▼
     c2c CLI         c2c-browser
        │                │
        │            Playwright
        │                │
        ▼                ▼
   C2C Bridge       ChatGPT Web
        ▲                │
        └────── MCP ─────┘
        │
        ▼
 Local Workspace
```

核心原则：

- **不 Fork `codex-with-chatgpt`**
- **不修改 MCP / Bridge / Workspace 核心**
- 原版 `codex-with-chatgpt` 继续作为 MCP / Workspace 后端
- 新增 `c2c-browser` 替换 Codex 专属浏览器控制层
- 所有 Agent 共用一份 Skill
- V1 只传输和读取文本，不实现 ChatGPT 文件下载

---

## 3. 实施细节拆解

### 3.1 保留 `codex-with-chatgpt` 后端

以下能力直接复用原项目，不修改：

```text
MCP Server
C2C Bridge
Workspace
Auth
Pairing
Tunnel
Execution Records
c2c CLI
```

继续使用现有 MCP 能力：

```text
workspace_info
list_directory
read_file
search_workspace
git_status
git_diff
test_status
execution_summary
execution_output
```

ChatGPT Web 仍然通过原有 MCP Connector 读取本地 Workspace。

---

### 3.2 Workspace 注册

所有 Agent 使用同一套方式确定当前项目。

先获取 Git 仓库根目录：

```bash
git rev-parse --show-toplevel
```

然后调用现有 C2C CLI：

```bash
c2c setup -w "<workspace-root>" --json
```

后续命令继续使用同一个 Workspace：

```bash
c2c status -w "<workspace-root>" --json
c2c record -w "<workspace-root>" ...
```

因此不需要重新设计 Agent ↔ MCP 通信。

Agent 只需要能够执行 Shell。

---

### 3.3 建立通用 Skill

只维护一份：

```text
c2c-agent-skill/
└─ SKILL.md
```

所有 Agent 共用同一份 Skill 内容。

Skill 只依赖：

```text
1. Agent 能执行 Shell
2. Agent 能调用 c2c CLI
3. Agent 能调用 c2c-browser CLI
```

不同 Agent 如果 Skill 安装目录不同，只做安装层面的复制或链接，不维护不同版本。

统一工作流：

```text
获取 repo root
↓
c2c setup
↓
c2c-browser 发送 INIT
↓
读取 PLAN
↓
Agent 执行修改 / 测试
↓
c2c record
↓
c2c-browser 发送 EXECUTED
↓
读取 REVIEW / PLAN / DONE
↓
继续执行直到 DONE
```

---

### 3.4 新建 `c2c-browser`

新建独立项目：

```text
c2c-browser/
├─ src/
│  ├─ browser.ts
│  ├─ chatgpt.ts
│  ├─ session.ts
│  └─ cli.ts
└─ package.json
```

内部使用 Playwright。

V1 只需要以下 CLI：

```bash
c2c-browser open
c2c-browser send "<message>"
c2c-browser wait
c2c-browser read
c2c-browser new
```

职责：

```text
open
→ 打开或恢复 ChatGPT 会话

send
→ 找到输入框
→ 输入文本
→ 发送

wait
→ 等待 ChatGPT 当前回复完成

read
→ 读取最新一条 Assistant 文本回复

new
→ 创建新的 ChatGPT 会话
```

V1 不实现：

```text
文件下载
附件处理
Artifact 回传
二进制产物
```

---

### 3.5 Browser Session（浏览器会话）

使用 Playwright Persistent Context 保存：

```text
Cookies
Local Storage
ChatGPT 登录状态
Browser Profile
```

例如：

```text
~/.c2c/browser-profile/
```

首次运行允许人工完成：

```text
登录
2FA
CAPTCHA
```

之后所有 Agent 共用同一个 Browser Profile。

---

### 3.6 ChatGPT 页面操作

优先使用稳定定位方式：

```text
role
accessible name
placeholder
稳定 locator
```

避免依赖：

```text
绝对 CSS selector
XPath
固定 DOM 层级
屏幕坐标
```

核心页面流程固定为：

```text
找到输入框
→ 输入 C2C 文本
→ 发送
→ 等待生成结束
→ 读取最新 Assistant 文本
```

需要加入：

```text
超时处理
重试
页面刷新恢复
会话失效检测
登录失效检测
```

---

### 3.7 C2C 协议

继续复用原协议：

```text
INIT
 ↓
PLAN
 ↓
EXECUTING
 ↓
EXECUTED
 ↓
REVIEW
 ↓
PLAN / DONE / BLOCKED
```

Agent 和 ChatGPT 之间只发送控制消息和摘要。

示例：

```text
[C2C]
STATE: EXECUTED
TASK_ID: xxx
ITERATION: 1

RESULT:
Implementation completed.

TESTS:
27 passed.

Please inspect the workspace and current git diff through MCP.
```

代码、Diff、文件内容不通过 Playwright 发送。

ChatGPT 自己通过 MCP 调用：

```text
git_diff
read_file
search_workspace
test_status
execution_output
```

---

### 3.8 Claude Code / Codex / Pi / OpenCode 接入

所有 Agent 使用同一份 Skill。

统一依赖：

```text
c2c CLI
+
c2c-browser CLI
+
统一 SKILL.md
```

不同 Agent 只需要把同一个 Skill 放到各自支持的 Skill / Instructions 目录中。

逻辑不分叉。

---

### 3.9 首次 ChatGPT MCP 配置

V1 保留人工配置。

流程：

```text
c2c setup -w <workspace>
        ↓
获取 MCP URL / Connector 信息
        ↓
用户在 ChatGPT Web 中创建 MCP Connector
        ↓
完成 OAuth / Pairing
        ↓
验证 workspace_info
```

V1 不自动化：

```text
Developer Mode
Connector 创建
OAuth
Pairing
Project 初始化
```

这些可以放到后续版本。

---

### 3.10 V1 范围

V1 只实现：

```text
统一 Skill
+
c2c-browser
+
Playwright 文本控制
+
复用现有 C2C MCP / Bridge
```

明确不做：

```text
ChatGPT 生成文件下载
Artifact Plane
MCP 写文件
自动首次 Connector 配置
多种浏览器后端
复杂 GUI 自动化
```

---

### 3.11 V1 最终交付物

只需要开发：

```text
1. c2c-browser
2. 通用 C2C SKILL.md
```

直接复用：

```text
原版 codex-with-chatgpt
```

最终结构：

```text
                    通用 SKILL.md
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Codex        Claude Code         Pi
          │              │              │
          └──────────────┼──────────────┘
                         │
                    Shell / CLI
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
           c2c CLI             c2c-browser
              │                     │
              ▼                 Playwright
         C2C Bridge                │
              ▲                    ▼
              └────── MCP ─── ChatGPT Web
              │
              ▼
        Local Workspace
```

这个方案可以在不修改 `codex-with-chatgpt` 核心源码的情况下，把原本偏 Codex 专用的协作模式扩展成所有支持 Shell 的 Coding Agent 都可复用的通用方案。
