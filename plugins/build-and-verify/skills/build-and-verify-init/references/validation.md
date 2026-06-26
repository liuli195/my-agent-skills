# Validation（校验）

本文件定义写入前和写入后的检查顺序。检查发现问题时仍允许用户继续写入配置，但必须列明问题、影响和建议。agent（代理）不安装依赖，不得未经授权安装依赖或修改外部环境。

## Order（顺序）

1. 写入前执行 targeted dependency checks（定向依赖检查）。
2. 写入前执行 environment checks（环境检查）。
3. 用户最终确认后，必要时备份已有配置。
4. 写入 `.build-and-verify/config.json`（配置文件）。
5. 写入后执行 config（配置）结构校验。

## Targeted Dependency Checks（定向依赖检查）

- command（命令）包含 `pytest -n`、`-n` pytest（Python 测试运行器）参数或 `--numprocesses` 时，检查 `pytest-xdist`（Pytest 并行插件）是否可用。
- command（命令）调用外部可执行入口时，检查该可执行入口是否可找到。
- paths（受影响路径）或 inputs（缓存输入）指向缺失文件或目录时，提示用户确认。
- `parallel: true`（并行检查）只说明 build-and-verify（构建与验证）runner（运行器）支持并行执行，不推断业务依赖。

## Environment Checks（环境检查）

- 确认目标仓库路径存在且是目录。
- 确认 `.build-and-verify`（配置目录）可创建或可写入。
- 覆盖已有配置时，确认备份目录可创建且备份路径仍在目标仓库内。
- 发现依赖或环境问题时，必须明确说明用户可以让 agent（代理）协助处理环境和外部依赖问题，但处理前必须获得用户明确授权。

报告格式必须包含：

- 问题。
- 影响。
- 建议。
- 是否阻止写入：默认不阻止，除非用户要求停止。

## Backup（备份）

覆盖已有 `.build-and-verify/config.json`（配置文件）前必须：

- 复制旧配置到 `.build-and-verify/backups/config-YYYYMMDD-HHMMSS.json`（备份配置文件）。
- 如果 backups（备份）目录不存在，必须先创建该目录，再复制旧配置。
- 确保 `.build-and-verify/.gitignore`（忽略规则）包含 `/backups/`。
- 在写入结果中报告备份路径。

## Config Structure Validation（配置结构校验）

写入后必须确认 `.build-and-verify/config.json`（配置文件）符合 runner（运行器）契约：

- 顶层是 object（对象）。
- `build.checks`（构建检查项）和 `verify.checks`（验证检查项）是 list（清单）。
- 每个 check（检查项）有非空且同分组唯一的 `id`（标识）。
- 每个 check（检查项）有非空 string（字符串）或 string list（字符串清单）形式的 command（命令）。
- `paths`（受影响路径）和 `inputs`（缓存输入）如果存在，必须是 string list（字符串清单），允许为空 string list（字符串清单）。
- check（检查项）的 `parallel`（并行检查）如果存在，必须是 boolean（布尔值）；`false`（否）等价于不声明 parallel（并行检查）。
- check（检查项）的 `timeoutSeconds`（超时秒数）如果存在，必须是大于 0 的 number（数字），不得是 boolean（布尔值）。
- `verify.maxParallel`（最大并行检查数）如果存在，必须是非负整数。
- `verify.timeoutSeconds`（超时秒数）如果存在，必须是大于 0 的 number（数字）。
