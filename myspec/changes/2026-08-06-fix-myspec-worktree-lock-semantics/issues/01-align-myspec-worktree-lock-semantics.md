# 01 — 对齐 MySpec 工作树锁语义并清理 Gate 3 外部来源

**What to build（构建内容）：** 让 MySpec 技能、正式工作规格和 Gate 3 流程对锁、开发绑定、发布模式工作树隔离及打包边界使用一致且准确的语义，并移除重复的外部规格收口技能。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] MySpec 技能将锁描述为当前目标工作树级别，并准确说明发布模式隔离和开发模式单一源码绑定。
- [ ] 正式 MySpec 工作规格描述同一目标工作树的运行互斥、发布模式不同工作树可并行，以及开发模式错绑阻断和串行限制。
- [x] Gate 3 继续只使用官方 MySpec 技能接口，不包含打包、安装或强制模式选择；完整验证和发布仍保留受控打包边界。
- [x] 运行现有 MySpec 公开 CLI 回归测试和规格校验，确认本次没有运行时行为变更。
- [x] 正式文档收口后删除外部 `archive-myspec-formal-delta` 技能，并确认没有遗留重复来源。

## Behavior evidence（行为证据）

- 技能文档变更：`8f680b9 修正自有规格工作树语义`、`4eabc79 补充开发绑定语义`。
- 规格入口冒烟：`myspec validate-main myspec/specs` 通过；当前主规格尚未应用 Delta（增量规格）。
- 固定基线快速验证：`build-and-verify verify --project . --base 1ccd6997` 通过；`checked` 非空，包含 `verify.local-build-contract` 和 `verify.my-spec`。
- Standards（规范）审查：无发现；Spec（规格）审查首轮发现开发绑定作用域表述不完整，已补充“机器级单一绑定、错绑阻断、切换后串行”，针对性复核结论为无阻断。
- 外部技能已删除，实体路径不存在；项目记忆中的历史说明保留，不构成重复技能来源。
- Gate 3 正式规格准备已完成 `state-init`、无冲突状态保存和 `validate-delta`，但预览生成因当前全局开发源码绑定指向主工作树、目标为本变更工作树而停止：`dev_source_worktree_mismatch`。运行状态和锁已保留，等待 Gate 3 恢复决策。
- 本次未修改运行时代码、打包入口或发布工作流。
