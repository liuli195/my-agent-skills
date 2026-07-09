## Why

PR Flow（拉取请求流程）已经能保守停止，但部分常见可恢复场景仍输出过粗的 stop state（停止状态），导致用户需要人工判断 EOF（连接提前结束）、checks（检查）等待、旧 review evidence（审查证据）残留和重复 `--fixes`（关闭引用参数）的下一步。

## What Changes

- 为只读 `gh pr view`（查看拉取请求）查询增加轻量 transient（临时失败）重试，默认次数可通过环境变量覆盖，不写入配置文件。
- `ruleset_merge_blocking`（规则集阻塞）后复用现有 checks（检查）等待逻辑；超时和轮询间隔继续使用 `.pr-flow/config.yaml`（配置文件）里的 `defaults.wait`（默认等待配置）。
- 已有 PR body（拉取请求正文）收到 `--fixes`（关闭引用参数）时，已包含则继续，缺失则只追加缺失 `Fixes #...`（关闭引用），不重写正文。
- `validate`（校验）发现废弃 `defaults.reviewGate.evidencePath`（审查证据路径）时输出 warning（警告），不恢复 local review gate（本地审查门禁）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `pr-flow-plugin`: 修正 PR Flow（拉取请求流程）可恢复停止状态、检查等待、正文关闭引用追加和废弃配置提示。

## Impact

- 代码：`plugins/pr-flow/skills/pr-flow/scripts/pr_flow.py`
- 测试：`tests/test_pr_flow_cli.py`
- 规格：`openspec/specs/pr-flow-plugin/spec.md` 的 delta（增量）变更
- 依赖：不新增依赖，不修改配置 schema（配置结构）
