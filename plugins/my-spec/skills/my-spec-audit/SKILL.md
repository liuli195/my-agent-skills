---
name: my-spec-audit
description: 对照 Git（版本管理）可见的整个仓库审计 MySpec（自有规格）。当用户要求从仓库行为补齐或审计规格时使用。
---

# my-spec-audit

以主规格为基准审计整个仓库；规格库不存在时按空库初始化。

执行前读取：

1. [公共规则](../my-spec/references/myspec-rules.md)
2. [仓库审计流程](../my-spec/references/audit.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作调用裸 `myspec ...` CLI（命令行程序），不得解析包内脚本路径。
