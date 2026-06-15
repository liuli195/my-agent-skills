# Validation Plan（验证计划）

- 校验所有必需 Guard Profile（守卫画像）文件存在。
- 校验 manifest（清单）包含 schema version（架构版本）、Runtime API version（运行时接口版本）、画像 ID 和文件索引。
- 校验 target model（目标模型）声明被守卫对象边界。
- 校验 state machine（状态机）引用已有状态、guard points（守卫点）和 artifacts（产物）。
- 校验 terminal states（终态）引用已有状态。
- 校验 Guard Brief（守卫简报）模板变量能由 latest brief（最新简报）字段填充。
- 校验显式激活只能通过 Session Focus Binding（会话焦点绑定）绑定 Guard Instance（守卫实例）。
- 校验缺少 Session Focus Binding（会话焦点绑定）时放行并写 `no_session_focus_instance` 审计。
