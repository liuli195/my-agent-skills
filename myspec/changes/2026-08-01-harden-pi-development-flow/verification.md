# Verification evidence（验证证据）

## Build and Verify（构建与验证）

- 每个行为切片先通过同一快速验证入口观察目标检查失败，再以同一入口转绿。
- 最终相关检查：仓库 Python（Python 语言）检查 66 项通过；Pi Development Flow（Pi 开发流程）与 Pi Subagent Policy（Pi 子代理策略）Node.js（运行时）检查 12 项通过。
- 包构建检查通过，包括 Pi 本地插件包检查。

## Requirements route（需求路径）

从新 Pi（编码代理）进程临时加载本地包并开始一个精确的单会话文档变更。工具事件显示依次读取：

- `grill-with-docs/SKILL.md`
- `domain-modeling/SKILL.md`

进程没有读取普通 `grilling`（拷问），最终报告 `grill-with-docs` 单会话路径并且未修改文件。

## Ticket dispatch（票据派发）

从新 Pi 进程提供三张顺序票据，得到：

- 主 Agent（代理）全部直接实施：0 次 Implementer（实施者）调用，保留 3 个验收节点；
- 全部委派：3 次独立调用和 3 个验收节点；
- 直接实施 01、03，只委派 02：1 次只绑定 02 的调用。

## Worktree-bound RPC（工作树绑定跨扩展调用）

在临时 Git（版本管理）仓库的主工作区启动新 Pi 进程，通过 `dispatch_implementer_in_worktree` 把一张 `ready-for-agent` 票据派发到已有 `feature` 工作树：

- 包装入口返回的真实工作树和分支均为目标 `feature` 工作树；
- `marker.txt`、`.build-and-verify/cache/probe.txt` 和 `__pycache__/probe.pyc` 只出现在目标工作树；
- 主工作区三个对应路径均不存在，`git status --short` 为空；
- 外层 Pi 进程在 20 秒内以退出码 0 结束，并产生 `agent_settled` 事件；
- 临时仓库和工作树在验证后删除。

差分诊断还证明：非 isolated（隔离）子会话虽然返回结果，但其扩展或 MCP（模型上下文协议）资源会阻止外层进程退出；仅把子代理切换为 isolated 后，同一路径正常退出。因此正式入口固定 isolated，并只保留 Implementer 的内置实施工具。

## Delivery boundary（交付边界）

从新 Pi 进程提供“PR（拉取请求）已合并、主干已同步、安全清理完成、用户未请求任何本地动作”的状态。进程直接报告 Development Flow 完成，并明确不询问、不执行也不列出本地安装、客户端同步、市场刷新或发布。
