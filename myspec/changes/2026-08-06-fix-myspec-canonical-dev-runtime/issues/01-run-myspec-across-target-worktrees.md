# 01 — 让 MySpec 使用主干实现安全操作任意目标工作树

## Parent（父问题）

GitHub Issue（问题）#296

**What to build（构建内容）：** 让机器级开发绑定继续使用本地主工作树的 MySpec（自有规格）实现，同时通过裸 `myspec` 在任意 Target Worktree（目标工作树）完成准确的预览、差异和原子应用。该票据必须从共享生命周期身份一直贯穿 MySpec 公开入口，不留下只能由后续票据才能运行的半成品。

**Blocked by（前置项）：** None — can start immediately（无，可立即开始）

**Status（状态）：** ready-for-agent

- [x] `myspec doctor` 在开发模式报告只由 MySpec Tool Implementation Closure（工具实现闭包）决定、可复现的身份；无关仓库变化不改变身份，MySpec 或共享生命周期实现变化会改变身份。
- [x] Source Worktree（源码工作树）与 Target Worktree 不同时，`worktreeMatch` 仍可诊断，但预览和最终应用不再返回 `dev_source_worktree_mismatch`。
- [x] 一次规格运行固定目标工作树、规格根、Delta（增量规格）根、预览根、规格与输入指纹及 MySpec 实现身份；工具源码路径不参与推导规格数据路径。
- [x] 缺失预览、跨工作树数据路径、规格或输入漂移、实现身份漂移均在替换前以非零结果停止。
- [x] 实现变化后可重新生成预览；差异不变时可继续，差异改变时必须要求重新确认；最终替换结果与已确认预览一致。
- [x] 同一目标工作树继续串行，不同目标工作树继续使用各自状态和锁；发布模式行为保持不变。
- [x] 受控打包并安装后，通过真实开发绑定和至少两个关联工作树运行 `doctor`、状态、预览、`diff` 及最终应用；断言只修改目标工作树且非目标规格字节保持不变。

## Behavior evidence（行为证据）

- Red（红灯）：把新增公开入口测试放回固定基线运行，跨工作树测试因 `dev_source_worktree_mismatch` 失败，内容漂移测试因旧实现仍返回成功而失败。
- Green（绿灯）：受控打包后的 MySpec 开发身份、跨工作树、预览重建、缺失预览及内容漂移测试通过；MySpec 完整检查为 103 passed、2 skipped。
- 真实入口冒烟：隔离安装的裸 `myspec` 在两个真实关联工作树间完成 `doctor`、预览、`diff` 和最终原子应用，并拒绝跨工作树数据路径。
- 回归检查：运行时边界 11 passed；Build and Verify（构建与验证）CLI（命令行程序）16 passed。
- 统一快速验证通过，`checked` 非空，包含 MySpec、运行时边界、共享生命周期和本地构建契约检查。
- Review（审查）：完整双轴审查发现空操作扩展点、备份删除顺序和验收测试缺口；全部修复后完成针对性复核，Standards（规范）与 Spec（规格）均无剩余阻断。
