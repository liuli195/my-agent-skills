# 01 — 新增跨平台 Full Verify（完整验证）汇总门禁

**What to build:** 让拉取请求的唯一必需 `Full Verify` 检查代表 Linux 和 Windows 平台验证的共同结果；只有所有平台任务成功时才通过，任一平台失败、取消或跳过时阻止合并。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] Linux 和 Windows 平台验证任务继续独立并行运行。
- [ ] 新的 `Full Verify` 汇总任务等待两个平台任务，并严格要求两个结果均为 `success`。
- [ ] 现有 `.pr-flow/config.yaml` 和 GitHub Ruleset（规则集）继续使用 `Full Verify` 作为唯一必需检查。
- [ ] 本地工作流契约检查先失败后通过，覆盖汇总任务依赖和失败结果处理。
- [ ] 真实拉取请求成功路径确认 `Full Verify` 指向汇总任务。
- [ ] 受控平台失败路径确认 `Full Verify` 失败或保持阻塞。
