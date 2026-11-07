## Root Cause

`PR status checks`（拉取请求状态检查）场景出现在 `CodeQL security check`（CodeQL 安全检查）之前，导致 agent（代理）会把 CodeQL（代码扫描工具）的分析任务和代码扫描结果当成普通必需检查来询问。

## Fix

把 `CodeQL security check`（CodeQL 安全检查）提前到 `branch protection`（分支保护）之后。用户选择不开启时直接进入普通 PR status checks（拉取请求状态检查），并明确不得提示 `Analyze Python` 或 `CodeQL` 这类 CodeQL（代码扫描工具）相关检查。用户选择开启时，再在后续 PR status checks（拉取请求状态检查）场景中把安全扫描相关检查降为高级额外选项，默认推荐非安全扫描门禁。

当前仓库配置同步为：CodeQL code scanning（CodeQL 代码扫描）通过 `Require code scanning results`（要求代码扫描结果）启用；required status checks（必需状态检查）只保留 `Full Verify`。

## Verification

- 聚焦测试覆盖 questionnaire（问答模板）顺序和 CodeQL（代码扫描工具）相关选择规则。
- `pr_flow.py validate` 校验当前 `.pr-flow/config.yaml`。
- 运行 full verify（全量验证）。
