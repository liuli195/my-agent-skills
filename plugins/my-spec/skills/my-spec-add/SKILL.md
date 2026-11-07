---
name: my-spec-add
description: 从 Agent（代理）为当前请求选取的相关证据新增或更新 MySpec（自有规格）。证据可来自会话、文档、代码或其他可读内容。
---

# my-spec-add

> 随包命令约定：本文件的 `myspec <参数>` 均指本次实际加载插件的 `node <verified-plugin-root>/bin/myspec.js <参数>` 参数数组，不是PATH中的裸命令。包根从当前官方技能/安装记录核实；没有真实路径时只取得本任务同版本官方完整资源，保留目录关系，缺失即停止，不猜缓存或回退旧全局npm。一次会话固定同一实现，不改变业务目标工作树。

根据当前请求处理 Agent（代理）选取的相关证据；不要求指定文档，也不执行全仓库审计。

执行前读取：

1. [公共规则](../my-spec/references/myspec-rules.md)
2. [新增文档流程](../my-spec/references/add-document.md)
3. [统一入口门禁](../my-spec/SKILL.md)

模板位于 `../my-spec/assets/`；所有确定性操作使用本次已核验插件的随包Node启动器；不得绕过启动器运行内部Python实现。

已有会话或草案不得覆盖、手动删锁。失败预览仅按统一入口的安全恢复边界，用 `myspec state-abort`（会话中止）核对精确身份、外部无活动确认及旧规格基线，先归档再解锁；未知或部分应用现场必须拒绝。显式导入归档 Delta（增量规格）后，重新分析、逐项决定、完整预览并等待新的最终确认。
