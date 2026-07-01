# Verification Report: fix-release-flow-dry-run-semantics

## Summary

| Dimension | Status |
| --- | --- |
| Completeness | PASS: release-flow dry-run（试运行）语义、preflight（发布前检查）投影检查和 OpenSpec（开放规格）合同已同步 |
| Correctness | PASS: 相关 CLI（命令行接口）测试和 OpenSpec（开放规格）校验通过 |
| Coherence | PASS: 保留 `publish --dry-run`（发布试运行）为纯预览，删除误导性落盘/投影 dry-run（试运行）入口 |

## Evidence

- `python -m pytest tests/test_release_flow_cli.py tests/test_release_flow_plugin_package.py -q`
  - Result: `49 passed`
- `openspec validate 2026-06-28-fix-release-flow-dry-run-semantics --strict`
  - Result: `Change '2026-06-28-fix-release-flow-dry-run-semantics' is valid`
- `openspec validate --specs --strict`
  - Result: `14 passed, 0 failed`
- `git diff --check`
  - Result: no whitespace errors

## Scope Checks

- `release-init`（发布初始化）不再接受 `--dry-run`（试运行），release plan（发布计划）不再写 `dryRun`（试运行标记）。
- `preflight`（发布前检查）不再接受 `--channel-tree`（通道树），改为在临时目录验证 projection（发布投影）可生成。
- `publish --dry-run`（发布试运行）仍保留，只输出明确字段，避免重复 `tag`（标签）。
- `ci-publish`（持续集成发布）不再接受 `--dry-run`（试运行），正式远端写入仍需 `--authorize-ci-publish`（授权持续集成发布）。

## Notes

- Comet（彗星流程）阶段推进命令在用户要求完整小改动流程后执行。
- 未派发子代理 code review（代码审查）；多代理工具要求用户明确要求子代理。本次改为主会话轻量审查。
- 本次没有新增依赖。
