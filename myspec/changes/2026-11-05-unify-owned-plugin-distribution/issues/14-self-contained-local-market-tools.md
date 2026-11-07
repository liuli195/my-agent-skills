# 14：统一开发市场中的命令工具完整安装

**状态：** implementation-verified-awaiting-gate-2
**前置：** 无新增阻塞票；复用已合并的九项市场、正式打包和实际运行入口。
**授权：** 第一门禁候选；尚未确认实施。

**交付行为：** 保留现有正式/开发双市场，通过既有构建入口为清单声明的命令工具准备自包含安装目录，由原生客户端安装；真实缓存内启动器可执行，正常运行不依赖旧全局 npm。

- [x] 共享实现只有一个维护源码，装配复用现有打包接缝；产物可重建，不新增市场或通用框架。
- [x] 构建缺失输入或失败时返回失败，上一份完整产物保留；不把旧目录作为本次成功。活跃市场来源产物保留，成功后只清本次暂存/已替代副本，不累计历史包；失败材料明确保留位置。
- [x] 首次构建及源码/共享输入变化后的重建可核验；同版本原生刷新按实际内容判断，必要时精确卸载/重装并保留范围、启用、数据和其他插件。
- [x] 两端真实缓存运行规格校验、构建验证的项目初始化/构建与运行身份诊断，不能以帮助或安装列表代替；不使用裸 PATH 工具。
- [x] 开发安装包携带构建来源证据；离线构建只装配及记录摘要，显式运行诊断核对缓存真实内容并复用原源码认证。源码提示不作为运行代码依赖，不依赖全局npm。
- [x] 已发布且闭包匹配的开发包返回原mode=dev四字段，PR持续集成选择精确源码提交；同正式版本号而内容不同的开发包不产生npm版本替代安装记录。
- [x] 源码闭包包含共享实现及打包器，不能混用缓存摘要口径；来源证据缺失、共享内容变化、未发布实现或缓存漂移时阻断PR，不静默降格正式模式。门禁二前用受控提交验证成功路径，新实现未发布应正确拒绝。
- [x] 正式两市场投影恢复标准来源；npm/正式完整包仍自包含，不携带开发产物路径。
- [x] 复用现有普通/真实测试接缝，守卫及60秒预算不放宽，不新增重型固定测试；仅补实际新增输入的追踪。
- [x] 保留当前回退入口、第三方、旧 npm、Matt 原目录、Wow 绑定及业务数据；最终清理和正式发布另行授权。

**真实公开入口：** 目标仓库既有构建入口 → 已有市场原生安装/刷新 → 客户端真实缓存内原 Node 启动器。此为一个完整纵向切片。
**开发可观察成功：** 生成完整包与安装包内容相符，两客户端相关公开命令可运行；正式投影及现有 npm 行为兼容。
**开发失败/恢复：** 输入、装配、刷新、身份或运行不符即停止受影响动作，保留证据并按已记录原生来源恢复，不手改缓存或删除未决内容。
**后续依赖：** 实施及限定审查后生成正式规格预览，门禁二再申请规格应用及 PR；发布、旧资产移除和最终环境清理不包含在本票开发授权中。

## Verification evidence (2026-11-07)

- Implementation: `74d24f8a52c59ee3f43442db45c60337d09c0e1f`; fixed baseline: `e90e4b7073636807b5552ec242223806048a004c`.
- Existing 17 fast groups passed in 28.315 seconds, without relaxing the 60-second budget or adding a verification group. Focused review-fix coverage: 12 passed.
- Independent GPT-6-A Standards and Spec reviews passed after fixing Windows publication/restore recovery and validation-before-publication.
- Codex and Claude native same-version refresh completed for both tools; complete installed file hashes match the assembled source. Package-owned Node launchers validated specifications and initialized/built consumer projects.
- A new Codex process discovered 19 enabled skills from all nine unified development plugins; Claude reports all nine enabled. Configuration comparison found only the intended two-tool changes.
- Controlled published-source fixture verifies the accepted development identity. The actual unpublished implementation correctly reports `no_published_match` without falling back to the same-version release identity; authentication must be checked again after the authorized push.
- Local raw evidence remains under `.local/ticket14-evidence/` and `.local/ticket14-verify-final/`; temporary clean verification worktree removed. Active `.local/dev-plugin-packages/` is required installation source, not disposable evidence. No cloud account writes, version release, legacy npm/skill removal, or Matt/Wow changes.
