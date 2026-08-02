# Pi（编码代理）本地兼容改动清单

本文件记录对 Pi（编码代理）本体及第三方插件所做的临时本地兼容改动，以及已确认但尚未修补的兼容问题。

## 使用规则

安装、更新或删除 Pi（编码代理）本体或任何插件时：

1. 操作前检查本清单，判断目标是否包含本地改动或依赖这些改动。
2. 更新后核对上游是否已经正式修复；不要直接重复套用旧改动。
3. 若上游未修复且问题仍可复现，经用户授权后重新应用并验证改动。
4. 删除插件时保留对应历史记录，将状态改为“已删除”或“无需继续跟踪”。
5. 新增、调整、撤销任何临时兼容改动时，同步更新本清单。
6. 不把普通配置、功能开发或一次性诊断步骤记作兼容改动。

## 已应用的临时兼容改动

### pi-chrome（Pi 浏览器插件）：重复加载警告静默处理

- **状态**：已应用，升级后必须复查
- **应用时版本**：`0.15.46`
- **文件**：`C:\Users\liuli\.pi\agent\npm\node_modules\pi-chrome\extensions\chrome-profile-bridge\index.ts`
- **位置**：当前版本第 675–677 行；定位锚点为 `const alreadyLoaded = globalState[PI_CHROME_GLOBAL_KEY]` 及其后的重复实例判断。
- **改动**：检测到重复实例时静默 `return`，删除该判断分支中原有的三行裸 `console.warn`。
- **原因**：非隔离子 Agent（子代理）重复初始化 pi-chrome（Pi 浏览器插件）时，裸警告会破坏 Pi TUI（终端用户界面）渲染，造成 AgentWidget（代理状态组件）旧帧重影。
- **验证结果**：在 `isolated: false` 条件下，警告和重影同时消失，FleetList（代理列表）恢复正常。
- **升级判断**：
  1. 检查该警告是否重新出现。
  2. 检查上游是否已正式处理重复加载。
  3. 保持原复现条件，不得擅自增加 `isolated: true` 等变量。
  4. 只有问题仍存在时才重新应用本地改动。

### @amaster.ai/pi-computer-use（桌面操作插件）：Windows 命名管道启动等待

- **状态**：已应用，升级后必须复查
- **应用时版本**：`0.1.7`（安装来源未固定版本）
- **文件**：`C:\Users\liuli\.pi\agent\npm\node_modules\@amaster.ai\pi-computer-use\dist\mcp-client.js`
- **位置**：`const socket = await this.ensureDaemon(layout, signal);` 之后、`const mcpArgs = [` 之前。
- **改动**：Windows（视窗系统）下，后台驱动报告就绪后等待 1.5 秒，再启动 MCP（模型上下文协议）连接。
- **原因**：插件原先看到 `daemon listening on` 后立即连接；此时命名管道尚未真正接受客户端，导致 `cua-driver connection failed (McpError)`。
- **上游比对**：从 npm（Node 软件包管理器）获取 `@amaster.ai/pi-computer-use@0.1.7` 官方 Tarball（归档包）；SHA-512 为 `838f5fd0763f54989e7cd52309aa72ae85b24b2b0ea41242463b95ee87ab8d9d56b7d73e4a25fe1e64582dcfa5bbf2bf70446086dc077310604b4e201a31bb68`。修复前，本地安装目录与官方归档包逐文件一致；目标文件 SHA-256 为 `2e5e07a0c21c201f52f404369b268ccf0af2de31551e39bd745d347f5ac89585`。
- **修复后差异**：仅 `dist/mcp-client.js` 在上述位置新增两行 Windows（视窗系统）等待逻辑；其余安装文件不变。修复后文件 SHA-256 为 `49108cbc62e58882f2c52970d25c2aad91e086f32cd162c9ec339576008c81dc`。
- **验证结果**：`computer_use_connect` 在修复前持续报告驱动不可用；修复后以更新后的真实 `CuaDriverClient`（驱动客户端）连接、发现 50 个工具，并关闭该临时客户端。
- **升级判断**：
  1. 检查上游是否加入 Windows（视窗系统）命名管道就绪探测、启动等待或连接重试。
  2. 先在未套用本地改动的新版上运行真实连接验证。
  3. 只有原问题仍可复现时才重新应用本地改动。
