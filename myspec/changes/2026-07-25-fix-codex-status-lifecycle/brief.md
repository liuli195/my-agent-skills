# Outcome

集中并安全化 `pi-codex-usage-status` 的状态栏写入，避免失效的 Pi 运行环境导致未捕获异常。

# Scope

- 修改 `plugins/pi-codex-usage-status/extensions/pi-codex-usage-status.ts`。
- 更新现有生命周期回归，使故障注入继续覆盖安全状态写入失效时的红灯路径。
- 所有 Codex 状态栏写入经由同一个安全函数。
- 保留现有计时器、请求取消和代次检查。
- 从真实 Pi 用户入口执行 `/reload` 回归。

# Non-goals

- 不引入运行环境所有者、代理、清理栈或新文件。
- 不更换 Codex 用量来源。
- 不重构用量解析与格式化。

# Acceptance examples

- 正常刷新后状态栏继续显示 Codex 用量。
- `/reload` 期间旧异步刷新即使碰到失效 UI，也不会导致 Pi 退出。
- reload 后新扩展实例继续刷新 Codex 状态。
- 会话关闭时安全清除状态。

# Constraints and invariants

- 不把 generation（代次）视为 Pi 运行环境有效性的证明。
- 状态栏异常只终止所属旧刷新，不传播为未捕获异常。
- 不触碰来源不明的未跟踪文件。

# Decisions

采用最小改动：在现有闭包内增加唯一、安全的状态栏写入函数；不做新架构重构。

# Open questions

无。

# Verification expectations

- 使用仓库 build-and-verify（构建与验证）入口。
- 从实际安装/发布形态启动 Pi，执行真实 `/reload`，确认进程存活且状态恢复。
