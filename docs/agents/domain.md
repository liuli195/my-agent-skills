# Domain Docs

本仓库是 single-context 布局。

在使用 `diagnose`、`tdd`、`improve-codebase-architecture` 等 engineering skills 前，先读取：

- 根目录的 `CONTEXT.md`，如果它存在
- `docs/adr/`，尤其是和当前工作范围相关的 ADR

如果 `CONTEXT.md` 不存在，直接继续，不要因此报错，也不要主动创建。只有用户明确要求，或文档工作流确实需要时，才创建它。

## 术语

输出 issue 标题、重构建议、假设、测试名等内容时，优先使用 `CONTEXT.md` 中已经定义的项目术语。

如果需要的术语还没有写入 `CONTEXT.md`，先按当前仓库已有文档表达，不要临时发明一套新叫法。

## ADR 冲突

如果输出内容和已有 ADR 冲突，需要明确指出冲突点，不要静默覆盖已有决定。
