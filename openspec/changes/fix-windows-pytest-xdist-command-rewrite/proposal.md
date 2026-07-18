## Why

Build and Verify 在为字符串形式的 Pytest 命令注入 `pytestXdistWorkers` 时使用 POSIX `shlex` 重新拼接命令，会破坏 Windows 命令中的反斜杠路径和 `set ...&&` 语法，导致原本有效的检查命令无法执行。当前测试只覆盖参数列表形式，未能发现该跨平台缺陷。

## What Changes

- 修正字符串命令的并行参数注入，保留原命令的 Windows shell 语法与路径。
- 增加 Windows 字符串命令回归测试，并保留参数列表命令的既有行为。
- 让使用方通过 `pytestXdistWorkers` 配置并行度，不再在命令中硬编码 `-n`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

无；这是既有 Build and Verify 运行时行为的缺陷修复，不改变规格要求。

## Impact

- `plugins/build-and-verify/skills/build-and-verify/scripts/build_and_verify_runner.py`
- `tests/test_build_and_verify_plugin.py`
- 发布后的 Build and Verify 插件及目标仓库运行时快照
