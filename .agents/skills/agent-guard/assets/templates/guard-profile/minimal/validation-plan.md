# Validation Plan（验证计划）

- 校验所有必需 Guard Profile（守卫画像）文件存在。
- 校验 manifest（清单）包含画像 ID、模式和文件索引。
- 校验 target model（目标模型）声明被守卫对象边界。
- 校验 activation（激活）规则包含来源、范围和初始状态。
- 校验 Subject Resolver（主体解析器）包含身份字段、必填字段和歧义策略。
- 校验 state machine（状态机）引用已有状态、guard points（守卫点）、artifacts（产物）和 signals（信号）。
- 校验 terminal states（终态）引用已有状态。
- 校验 Hook Bindings（钩子绑定）引用已有 transitions（状态转换）和 guard points（守卫点）。
- 校验 Guard Brief（守卫简报）模板变量能由 latest brief（最新简报）字段填充。
- 校验显式激活能按 Subject Resolver（主体解析器）创建或匹配 Guard Instance（守卫实例）。
- 校验缺少 required field（必填字段）时只返回 `no_subject_match` 并写审计。
