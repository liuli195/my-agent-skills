# 独立命令工具

仅在用户请求独立命令工具本身时，从插件清单的包管理能力取得包名和程序命令；需要 explicit user authorization（显式授权）才安装或更新。命令工具生命周期识别统一市场安装后保留该来源，不卸载、切换或更新其插件资源。

例如 `build-and-verify doctor`、`build-and-verify init`、`build-and-verify update` 是独立命令工具入口；其他带命令工具的清单项使用同样的能力规则。插件检查、安装、更新和来源切换仍走通用市场流程。

不检查、刷新、删除、提交或报告仓库 `.build-and-verify/runtime/` 快照。
