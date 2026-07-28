---
name: my-spec-add
description: 从 Agent（代理）为当前请求选取的相关证据新增或更新 MySpec（自有规格）。证据可来自会话、文档、代码或其他可读内容。
---

# my-spec-add

根据当前请求处理 Agent（代理）选取的相关证据；不要求指定文档，也不执行全仓库审计。

执行前读取：

1. [公共规则](../my-spec/references/myspec-rules.md)
2. [新增文档流程](../my-spec/references/add-document.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作调用 `../my-spec/scripts/spec_ops.py`。
