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

模板位于 `../my-spec/assets/`；所有确定性操作调用裸 `myspec ...` CLI（命令行程序），不得解析包内脚本路径。

已有会话或草案不得覆盖、手动删锁。失败预览仅按统一入口的安全恢复边界，用 `myspec state-abort`（会话中止）核对精确身份、外部无活动确认及旧规格基线，先归档再解锁；未知或部分应用现场必须拒绝。显式导入归档 Delta（增量规格）后，重新分析、逐项决定、完整预览并等待新的最终确认。
