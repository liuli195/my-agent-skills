# Agent Guard（代理守卫）

Agent Guard（代理守卫）定义可安装到用户级 agent skills（代理技能）的守卫能力。它用 Guard Profile（守卫画像）描述流程边界，用 Runtime（运行时）解释和执行这些边界。

## Language（语言）

**状态权限**:
某个 Guard Instance（守卫实例）在当前状态下对操作给出的 `allow`、`ask` 或 `deny` 约束。
_Avoid（避免使用）_: blocking mode（阻断模式）, 权限开关

**Dynamic Permission Management（动态权限管理）**:
未来可能引入的状态权限变更入口；当前阶段不是独立组件，也不是当前验收项。
_Avoid（避免使用）_: 权限服务, 独立权限管理器
