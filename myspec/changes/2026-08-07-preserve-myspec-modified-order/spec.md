# 保持 MySpec 修改需求顺序

## Problem Statement（问题陈述）

MySpec（自有规格）应用同一 capability（能力）内的 `MODIFIED`（修改）Delta（增量规格）时，会把已有 Requirement（需求）从原位置移动到能力文件末尾。正文语义虽然正确，但预览和完整差异会包含纯位置移动造成的大段删除与新增，增加 Gate 3（第三门禁）的人工审阅成本。

## Solution（解决方案）

同一 capability（能力）内修改已有 Requirement（需求）时，在原有顺序位置替换正文。跨能力修改继续移动到目标能力；`ADDED`（新增）、`REMOVED`（删除）和 `RENAMED`（改名）保持现有行为。预览、差异、正式应用和重复执行都通过现有裸 `myspec` CLI（命令行程序）入口保持一致。

## User Stories（用户故事）

1. 作为规格维护者，我希望修改已有 Requirement（需求）时保持原顺序，以便完整差异只展示真实正文变化。
2. 作为 Gate 3（第三门禁）审查者，我希望预览不包含纯位置移动，以便减少无关审阅内容。
3. 作为 MySpec（自有规格）使用者，我希望其他 Delta（增量规格）操作和重复执行行为保持稳定，以便现有流程不受影响。

## Implementation Decisions（实施决策）

- 在现有 Delta（增量规格）合并实现内部区分同能力修改和跨能力移动。
- 同能力 `MODIFIED`（修改）直接覆盖已有 Requirement（需求）正文，不先删除。
- 跨能力 `MODIFIED`（修改）继续删除来源并加入目标能力。
- 不拆分操作处理器，不引入新的顺序模型、Module（模块）、Interface（接口）或 Seam（接缝）。
- 不改变 `ADDED`（新增）、`REMOVED`（删除）、`RENAMED`（改名）、渲染、校验、原子替换或失败恢复行为。

## Testing Decisions（测试决策）

- 最高公开测试 Seam（接缝）是打包并隔离安装后的裸 `myspec` CLI（命令行程序）。
- 通过公开命令完成状态初始化、冲突记录、预览、差异、正式应用和重复执行，不直接测试私有合并函数。
- 首部和中部 Requirement（需求）用于稳定暴露原缺陷；尾部 Requirement（需求）用于保护完整位置行为。
- 断言 Requirement（需求）标题顺序、正文真实变化以及差异中不存在纯位置移动。
- 覆盖跨能力 `MODIFIED`（修改）以及其他 Delta（增量规格）操作的现有语义。
- 使用 Build and Verify（构建与验证）完成风险匹配验证，并要求快速验证至少选中一项检查且通过。

## Out of Scope（范围外）

- Issue #300 的 Windows（视窗系统）工作区状态问题。
- 改变 `RENAMED`（改名）后的标题位置。
- 重构完整 Delta（增量规格）操作模型。
- 修改文件元数据、行尾、目录替换或 Git（版本管理）索引行为。
- 发布、版本升级、本地安装或客户端同步。

## Further Notes（补充说明）

本变更不引入新的领域术语，也不需要 ADR（架构决策记录）。这是可观察运行行为缺陷，按 Standard（标准）开发流程交付。关联 GitHub Issue（问题）：#299。
