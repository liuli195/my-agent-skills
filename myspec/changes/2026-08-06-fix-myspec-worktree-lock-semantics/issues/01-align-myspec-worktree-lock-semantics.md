# 01 — 对齐 MySpec 工作树锁语义并清理 Gate 3 外部来源

**What to build（构建内容）：** 让 MySpec 技能、正式工作规格和 Gate 3 流程对锁、开发绑定、发布模式工作树隔离及打包边界使用一致且准确的语义，并移除重复的外部规格收口技能。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] MySpec 技能将锁描述为当前目标工作树级别，并准确说明发布模式隔离和开发模式单一源码绑定。
- [x] 正式 MySpec 工作规格描述同一目标工作树的运行互斥、发布模式不同工作树可并行，以及开发模式错绑阻断和串行限制。
- [x] Gate 3 继续只使用官方 MySpec 技能接口，不包含打包、安装或强制模式选择；完整验证和发布仍保留受控打包边界。
- [x] 运行现有 MySpec 公开 CLI 回归测试和规格校验，确认本次没有运行时行为变更。
- [ ] 正式文档收口后删除外部 `archive-myspec-formal-delta` 技能，并确认没有遗留重复来源。

## Behavior evidence（行为证据）

- 文档与正式规格变更：`8f680b9 修正自有规格工作树语义`。
- 规格入口冒烟：`myspec validate-main myspec/specs` 通过。
- 固定基线快速验证：`build-and-verify verify --project . --base 1ccd6997` 通过；`checked` 非空，包含 `verify.local-build-contract`、`verify.myspec` 和 `verify.my-spec`。
- 本次未修改运行时代码、打包入口或发布工作流；外部技能删除保留到 Gate 3 收口动作。
