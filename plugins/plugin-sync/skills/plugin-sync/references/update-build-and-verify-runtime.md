# Build and Verify CLI（命令行程序）委托

Build and Verify（构建与验证）的 Agent（代理）资源、模式和版本由 `build-and-verify` CLI（命令行程序）管理。

默认只读：按用户请求运行 `build-and-verify doctor`。初始化或更新仅在用户 explicit user authorization（显式授权）后运行 `build-and-verify init` 或 `build-and-verify update`。

不得检查、刷新、删除、提交或报告 `.build-and-verify/runtime/` 仓库运行时快照；也不得扫描或改写既有调用方。
