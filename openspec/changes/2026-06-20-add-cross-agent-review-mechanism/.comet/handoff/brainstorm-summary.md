# Brainstorm Summary

- Change: add-cross-agent-review-mechanism
- Date: 2026-06-20

## 确认的技术方案

新增独立 `plugins/cross-agent-review` plugin，提供 `cross-agent-review` skill 和一个最小 Python 脚本。首版保持单脚本、少配置，不做 runner framework，不做 CLI fallback。

运行流程：

1. 调用方先提交代码并运行测试。
2. Review 脚本通过 CLI 参数接收 `change`、`base_ref`、`head_ref`、diff、spec、design、tasks 和 tests 结果文件。
3. 启动前、派发前、生成 `review-pass.json` 前都要求 worktree 干净，且当前 `HEAD == head_ref`。
4. 脚本用 Claude Agent SDK 并行派发固定 reviewer。
5. reviewer 返回结构化 findings，脚本汇总并生成报告。
6. 只有 `blocking_findings == 0` 且 subject 仍干净时生成 `review-pass.json`。

固定 reviewer：

- spec alignment
- implementation correctness
- tests and edge cases
- risk review

Claude Agent SDK 是硬依赖，但不由 plugin 自动安装。脚本先尝试当前 Python，再探测 `~/.claude/security/agent-sdk-venv/Scripts/python.exe`，并支持显式 `--sdk-python` 或环境变量指定。Reviewer 允许只读访问 workspace，但必须禁用写入工具。

默认输出目录为 `.local/cross-agent-review/<change>/<head_ref>/`，可用 `--output-dir` 覆盖。每次 review 都生成 `review-report.md` 和 `review-results.json`；通过时额外生成 `review-pass.json`。

## 关键取舍与风险

- 独立 plugin 边界清晰，后续 Agent Guard 只消费 pass marker。
- 只用 SDK 简化派发与结构化输出，但 `claude-agent-sdk` 成为硬依赖。
- 不自动安装 SDK，避免插件执行隐式环境修改；缺失时给出明确报错。
- Clean commit subject 绑定会降低临时审查灵活性，但能防止旧 pass marker 被复用到未审查 diff。
- 修复 review 发现的问题后必须提交形成新的 `head_ref`，再重新运行完整 review；未提交修复只能运行本地测试，不能生成或满足 `review-pass.json`。
- Cross-agent review 是 Comet verify 前的独立审查证据，不运行构建/测试、不推进 Comet phase、不替代 `/comet-verify`。
- `.comet/build-check.sh` 是本仓库定制快速回归入口，不是 Comet 自动生成文件；后续新增插件测试后应更新或补充仓库验证入口。

## 测试策略

- CLI 必填参数和输入文件存在性。
- SDK 解析：当前 Python 可 import、常见 Claude SDK venv 可用、显式 `--sdk-python` 可用、SDK 缺失时报错。
- Reviewer 只读权限：SDK options 不允许 `Edit`、`Write` 等写入工具。
- Subject 绑定：启动时 dirty 拒绝、派发前 dirty 拒绝、生成 pass marker 前 dirty 拒绝、当前 `HEAD` 与 `head_ref` 不一致拒绝。
- Reviewer result：无 findings、WARNING/SUGGESTION、IMPORTANT/CRITICAL、非法 JSON、超时。
- Aggregation：按 `severity + location + summary` 精确去重并计算 `blocking_findings`。
- Outputs：报告和 results 总是生成；pass marker 只在无阻塞 findings 且 subject 干净时生成。
- Pass marker 完整性：包含 `change`、`base_ref`、`head_ref`、`blocking_findings`、`report`、`report_hash`，且 `report_hash` 匹配报告内容。
- Risk review disabled：报告记录 skipped 和原因。
- 输出目录：默认 `.local/cross-agent-review/<change>/<head_ref>/` 和 `--output-dir` 覆盖。

## Spec Patch

需要回写 OpenSpec delta spec，补充：

- 独立 `cross-agent-review` plugin/skill 发布形态。
- 首版只使用 Claude Agent SDK，不自动安装 SDK。
- Reviewer 只读 workspace。
- Review subject 必须是 clean commit，且当前 `HEAD == head_ref`。
- 修复问题后必须提交并重新 review 新 `head_ref`。
- 默认输出目录和 `--output-dir` 覆盖。
- `review-report.md`、`review-results.json` 和 `review-pass.json` 的生成规则。
- `review-pass.json` 必须包含 report hash 和当前 subject 信息，避免复用。
- SDK 缺失、dirty worktree、HEAD mismatch、reviewer 超时/非法 JSON 等失败路径。
- Cross-agent review 不运行构建/测试、不推进 Comet phase、不替代 Comet verify。
