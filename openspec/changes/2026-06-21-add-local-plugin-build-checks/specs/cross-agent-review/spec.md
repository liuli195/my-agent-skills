## ADDED Requirements

### Requirement: review input snapshots
系统 MUST 在 review output（审查输出）目录中保存本次 review（审查）使用的输入文件快照，方便复现和排障。

#### Scenario: 输入快照写入输出目录
- **WHEN** cross-agent-review（跨代理审查）运行并接收 diff、spec、design、tasks 和 tests 输入文件
- **THEN** 系统 MUST 在输出目录的 `inputs/` 子目录写入 `diff.patch`、`spec.md`、`design.md`、`tasks.md` 和 `tests.txt`

#### Scenario: reviewer 使用输入快照
- **WHEN** reviewer agent（审查代理）收到审查提示
- **THEN** 提示中的 diff、spec、design、tasks 和 tests 内容 MUST 来自输出目录中的输入快照
