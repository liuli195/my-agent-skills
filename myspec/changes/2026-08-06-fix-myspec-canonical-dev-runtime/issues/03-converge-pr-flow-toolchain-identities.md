# 03 — 让 PR Flow 使用双工具身份稳定完成同工作树交付

## Parent（父问题）

GitHub Issue（问题）#296

**What to build（构建内容）：** 让 PR Flow（拉取请求流程）只消费已经分别通过公开入口验证的 MySpec（自有规格）和 Build and Verify（构建与验证）身份，在源码工作树与交付目标为同一工作树时完成工具链记录、CI（持续集成）同步和稳定收敛。

**Blocked by（前置项）：** 01 — 让 MySpec 使用主干实现安全操作任意目标工作树；02 — 让 Build and Verify 使用开发实现身份管理验证缓存

**Status（状态）：** ready-for-agent

- [x] PR Flow 分别记录 MySpec 与 Build and Verify 的开发或发布 Toolchain Identity（工具链身份），不重新实现插件自己的身份算法。
- [x] 开发身份引用能够重建对应 Tool Implementation Closure（工具实现闭包）的稳定源码提交，而不是整个工作树当前提交。
- [x] 工具链记录、生成工作流、规格和普通配置提交不改变任一工具身份；修改一个插件只更新对应记录，修改共享生命周期输入同时更新两个记录。
- [x] 删除 `toolchain_same_worktree_unsupported` 临时阻断；源码工作树与 PR 目标为同一工作树时可继续完成流程。
- [x] 第一次工具链同步写入所需记录和工作流；在工具实现未变时再次运行不得产生身份或文件差异。
- [x] 找不到可由 CI 检出的精确实现提交时，PR Flow 在写入或交付前失败关闭并报告可恢复原因。
- [x] 通过公开 PR Flow `init` 和交付入口完成同工作树真实冒烟，验证双工具身份、第一次同步、第二次收敛及单工具变化行为。

## Behavior evidence（行为证据）

- Red（红灯）：把同工作树公开初始化测试放回票据起始提交运行，旧实现返回 `toolchain_same_worktree_unsupported`。
- Green（绿灯）：公开 PR Flow 测试覆盖同工作树初始化与交付、首次同步、二次无差异、单插件身份变化、共享生命周期同时变化、非法身份和不可复现提交。
- 真实入口冒烟：隔离 Git（版本管理）仓库通过公开 `init`、`complete` 和 `tweak` 入口写入双工具记录；第二次运行不新增同步提交，缺少实现提交时在任何工具链写入前停止。
- 工具身份回归：MySpec 在 Windows 换行和本地尚无远端新 head 对象时仍保留无关提交之前的已发布实现提交，并拒绝脏、仅本地或远端已删除实现；Build and Verify 报告受控已发布实现提交。
- 统一快速验证通过，`checked` 非空，包含 PR Flow、MySpec、Build and Verify、共享生命周期和运行时边界检查。
- Review（审查）：最终双轴审查发现 Windows 换行会破坏提交匹配，以及陈旧或本地未知的远端 head 会造成错误身份判断；增加规范化、来源恢复和按当前远端 head 安全取证后完成针对性复核，Standards（规范）与 Spec（规格）均无剩余阻断。
